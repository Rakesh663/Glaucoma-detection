"""
A/B Testing framework with statistical analysis
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import hashlib
import random
from dataclasses import dataclass
from scipy import stats
import numpy as np

from api.utils.redis_client import redis_client
from api.utils.logging_config import logger


class ABTestVariant(str, Enum):
    """A/B test variant identifiers"""
    CONTROL = "control"
    VARIANT_A = "variant_a"
    VARIANT_B = "variant_b"
    VARIANT_C = "variant_c"


class ABTestStatus(str, Enum):
    """A/B test status"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class ABTestConfig:
    """A/B test configuration"""
    test_id: str
    name: str
    description: str
    variants: Dict[ABTestVariant, Dict[str, Any]]  # variant -> config
    traffic_allocation: Dict[ABTestVariant, float]  # variant -> percentage
    status: ABTestStatus = ABTestStatus.DRAFT
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    min_sample_size: int = 1000
    significance_level: float = 0.05  # 95% confidence


@dataclass
class ABTestResult:
    """Results for a single variant"""
    variant: ABTestVariant
    impressions: int
    conversions: int
    conversion_rate: float
    revenue: float = 0.0
    avg_response_time: float = 0.0


class ABTestingService:
    """
    Service for A/B testing with statistical analysis
    """

    # Redis key prefixes
    TEST_CONFIG_PREFIX = "ab_test:config"
    TEST_ASSIGNMENT_PREFIX = "ab_test:assignment"
    TEST_METRICS_PREFIX = "ab_test:metrics"

    @staticmethod
    async def create_test(config: ABTestConfig) -> bool:
        """Create a new A/B test"""
        try:
            # Validate traffic allocation
            total_allocation = sum(config.traffic_allocation.values())
            if not (0.99 <= total_allocation <= 1.01):  # Allow small floating point errors
                raise ValueError(f"Traffic allocation must sum to 100%, got {total_allocation * 100}%")

            # Store config in Redis
            config_key = f"{ABTestingService.TEST_CONFIG_PREFIX}:{config.test_id}"
            config_data = {
                "test_id": config.test_id,
                "name": config.name,
                "description": config.description,
                "variants": {k.value: v for k, v in config.variants.items()},
                "traffic_allocation": {k.value: v for k, v in config.traffic_allocation.items()},
                "status": config.status.value,
                "min_sample_size": config.min_sample_size,
                "significance_level": config.significance_level
            }

            await redis_client.set_json(config_key, config_data)

            logger.info(
                f"Created A/B test: {config.test_id}",
                test_id=config.test_id,
                variants=list(config.variants.keys())
            )

            return True

        except Exception as e:
            logger.error(f"Failed to create A/B test: {str(e)}", exc_info=True)
            return False

    @staticmethod
    async def assign_variant(
        test_id: str,
        user_id: str,
        sticky: bool = True
    ) -> Optional[ABTestVariant]:
        """
        Assign a user to a test variant

        Args:
            test_id: ID of the A/B test
            user_id: User identifier
            sticky: If True, user gets same variant on subsequent calls

        Returns:
            Assigned variant or None if test not found
        """
        try:
            # Check if user already assigned (sticky sessions)
            if sticky:
                assignment_key = f"{ABTestingService.TEST_ASSIGNMENT_PREFIX}:{test_id}:{user_id}"
                existing_assignment = await redis_client.get(assignment_key)

                if existing_assignment:
                    return ABTestVariant(existing_assignment)

            # Get test config
            config_key = f"{ABTestingService.TEST_CONFIG_PREFIX}:{test_id}"
            config_data = await redis_client.get_json(config_key)

            if not config_data:
                logger.warning(f"A/B test not found: {test_id}")
                return None

            # Check if test is running
            if config_data.get("status") != ABTestStatus.RUNNING.value:
                logger.debug(f"A/B test not running: {test_id}")
                return None

            # Deterministic assignment based on user_id hash
            traffic_allocation = {
                ABTestVariant(k): v
                for k, v in config_data["traffic_allocation"].items()
            }

            variant = ABTestingService._assign_variant_by_hash(
                user_id,
                traffic_allocation
            )

            # Store assignment
            if sticky:
                assignment_key = f"{ABTestingService.TEST_ASSIGNMENT_PREFIX}:{test_id}:{user_id}"
                await redis_client.set(assignment_key, variant.value, expire=86400 * 30)  # 30 days

            # Increment impression counter
            await ABTestingService._record_impression(test_id, variant)

            return variant

        except Exception as e:
            logger.error(f"Failed to assign variant: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def _assign_variant_by_hash(
        user_id: str,
        traffic_allocation: Dict[ABTestVariant, float]
    ) -> ABTestVariant:
        """
        Assign variant using consistent hashing

        This ensures the same user always gets the same variant
        """
        # Create hash from user_id
        hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)

        # Normalize to 0-1
        normalized = (hash_value % 10000) / 10000.0

        # Assign based on traffic allocation
        cumulative = 0.0
        for variant, allocation in sorted(traffic_allocation.items()):
            cumulative += allocation
            if normalized < cumulative:
                return variant

        # Fallback (should never reach here)
        return ABTestVariant.CONTROL

    @staticmethod
    async def _record_impression(test_id: str, variant: ABTestVariant):
        """Record an impression for a variant"""
        metrics_key = f"{ABTestingService.TEST_METRICS_PREFIX}:{test_id}:{variant.value}:impressions"
        await redis_client.incr(metrics_key)

    @staticmethod
    async def record_conversion(
        test_id: str,
        user_id: str,
        value: float = 1.0
    ):
        """
        Record a conversion event

        Args:
            test_id: ID of the A/B test
            user_id: User identifier
            value: Optional conversion value (revenue, etc.)
        """
        try:
            # Get user's variant assignment
            assignment_key = f"{ABTestingService.TEST_ASSIGNMENT_PREFIX}:{test_id}:{user_id}"
            variant_str = await redis_client.get(assignment_key)

            if not variant_str:
                logger.warning(f"No variant assignment found for user {user_id} in test {test_id}")
                return

            variant = ABTestVariant(variant_str)

            # Increment conversion counter
            conversions_key = f"{ABTestingService.TEST_METRICS_PREFIX}:{test_id}:{variant.value}:conversions"
            await redis_client.incr(conversions_key)

            # Add to revenue if value provided
            if value > 0:
                revenue_key = f"{ABTestingService.TEST_METRICS_PREFIX}:{test_id}:{variant.value}:revenue"
                current_revenue = await redis_client.get(revenue_key) or "0"
                new_revenue = float(current_revenue) + value
                await redis_client.set(revenue_key, str(new_revenue))

            logger.info(
                f"Recorded conversion for A/B test",
                test_id=test_id,
                variant=variant.value,
                value=value
            )

        except Exception as e:
            logger.error(f"Failed to record conversion: {str(e)}", exc_info=True)

    @staticmethod
    async def get_test_results(test_id: str) -> Dict[ABTestVariant, ABTestResult]:
        """Get current results for all variants in a test"""
        try:
            # Get test config
            config_key = f"{ABTestingService.TEST_CONFIG_PREFIX}:{test_id}"
            config_data = await redis_client.get_json(config_key)

            if not config_data:
                return {}

            results = {}
            variants = [ABTestVariant(v) for v in config_data["variants"].keys()]

            for variant in variants:
                # Get metrics
                impressions_key = f"{ABTestingService.TEST_METRICS_PREFIX}:{test_id}:{variant.value}:impressions"
                conversions_key = f"{ABTestingService.TEST_METRICS_PREFIX}:{test_id}:{variant.value}:conversions"
                revenue_key = f"{ABTestingService.TEST_METRICS_PREFIX}:{test_id}:{variant.value}:revenue"

                impressions = int(await redis_client.get(impressions_key) or "0")
                conversions = int(await redis_client.get(conversions_key) or "0")
                revenue = float(await redis_client.get(revenue_key) or "0.0")

                conversion_rate = conversions / impressions if impressions > 0 else 0.0

                results[variant] = ABTestResult(
                    variant=variant,
                    impressions=impressions,
                    conversions=conversions,
                    conversion_rate=conversion_rate,
                    revenue=revenue
                )

            return results

        except Exception as e:
            logger.error(f"Failed to get test results: {str(e)}", exc_info=True)
            return {}

    @staticmethod
    def analyze_results(
        control_result: ABTestResult,
        variant_result: ABTestResult,
        significance_level: float = 0.05
    ) -> Dict[str, Any]:
        """
        Perform statistical analysis of A/B test results

        Uses Z-test for comparing conversion rates

        Returns:
            Dictionary with statistical analysis results
        """
        try:
            # Calculate pooled standard error
            n1, n2 = control_result.impressions, variant_result.impressions
            p1, p2 = control_result.conversion_rate, variant_result.conversion_rate

            if n1 == 0 or n2 == 0:
                return {
                    "error": "Insufficient data",
                    "statistical_significance": False
                }

            # Pooled probability
            p_pool = (control_result.conversions + variant_result.conversions) / (n1 + n2)

            # Standard error
            se = np.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))

            # Z-score
            z_score = (p2 - p1) / se if se > 0 else 0

            # P-value (two-tailed test)
            p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))

            # Confidence interval for difference
            ci = 1.96 * se  # 95% confidence interval

            # Relative improvement
            relative_improvement = ((p2 - p1) / p1 * 100) if p1 > 0 else 0

            # Statistical significance
            is_significant = p_value < significance_level

            # Winner determination
            if is_significant:
                winner = variant_result.variant if p2 > p1 else control_result.variant
            else:
                winner = None

            return {
                "control_conversion_rate": p1,
                "variant_conversion_rate": p2,
                "relative_improvement_pct": relative_improvement,
                "z_score": z_score,
                "p_value": p_value,
                "confidence_interval": ci,
                "statistical_significance": is_significant,
                "significance_level": significance_level,
                "winner": winner.value if winner else None,
                "sample_sizes": {
                    "control": n1,
                    "variant": n2
                },
                "recommendation": ABTestingService._get_recommendation(
                    is_significant,
                    p1,
                    p2,
                    n1,
                    n2,
                    relative_improvement
                )
            }

        except Exception as e:
            logger.error(f"Failed to analyze results: {str(e)}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    def _get_recommendation(
        is_significant: bool,
        p_control: float,
        p_variant: float,
        n_control: int,
        n_variant: int,
        improvement: float
    ) -> str:
        """Generate recommendation based on test results"""
        min_sample = 1000

        if n_control < min_sample or n_variant < min_sample:
            return f"Continue test. Need at least {min_sample} samples per variant."

        if not is_significant:
            return "No significant difference detected. Consider running test longer or increasing sample size."

        if is_significant and p_variant > p_control:
            return f"Variant shows {improvement:.1f}% improvement and is statistically significant. Recommend rolling out to 100%."

        if is_significant and p_variant < p_control:
            return f"Variant shows {abs(improvement):.1f}% decrease and is statistically significant. Recommend sticking with control."

        return "Results inconclusive. Continue monitoring."


# Example usage:
"""
# Create test
config = ABTestConfig(
    test_id="model_v2_test",
    name="Model V2 Performance Test",
    description="Compare old vs new model accuracy",
    variants={
        ABTestVariant.CONTROL: {"model": "v1"},
        ABTestVariant.VARIANT_A: {"model": "v2"}
    },
    traffic_allocation={
        ABTestVariant.CONTROL: 0.5,
        ABTestVariant.VARIANT_A: 0.5
    },
    status=ABTestStatus.RUNNING
)

await ABTestingService.create_test(config)

# Assign user to variant
variant = await ABTestingService.assign_variant("model_v2_test", "user_123")

# Record conversion
await ABTestingService.record_conversion("model_v2_test", "user_123", value=1.0)

# Get results
results = await ABTestingService.get_test_results("model_v2_test")

# Analyze
analysis = ABTestingService.analyze_results(
    results[ABTestVariant.CONTROL],
    results[ABTestVariant.VARIANT_A]
)
"""
