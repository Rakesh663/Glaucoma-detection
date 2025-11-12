#!/bin/bash
# Performance test runner using Locust

set -e

echo "======================================"
echo "Glaucoma API Performance Tests"
echo "======================================"

# Check if locust is installed
if ! command -v locust &> /dev/null; then
    echo "Installing Locust..."
    pip install locust
fi

# Default values
HOST=${HOST:-http://localhost:8000}
USERS=${USERS:-100}
SPAWN_RATE=${SPAWN_RATE:-10}
RUN_TIME=${RUN_TIME:-5m}
TEST_TYPE=${1:-load}

echo "Test Configuration:"
echo "  Host: $HOST"
echo "  Users: $USERS"
echo "  Spawn Rate: $SPAWN_RATE"
echo "  Run Time: $RUN_TIME"
echo "  Test Type: $TEST_TYPE"
echo ""

case $TEST_TYPE in
    load)
        echo "Running Load Test..."
        locust -f tests/test_performance.py \
            --host=$HOST \
            --users=$USERS \
            --spawn-rate=$SPAWN_RATE \
            --run-time=$RUN_TIME \
            --headless \
            --html=performance_report.html
        ;;

    stress)
        echo "Running Stress Test (high load)..."
        locust -f tests/test_performance.py \
            --host=$HOST \
            --users=500 \
            --spawn-rate=50 \
            --run-time=10m \
            --headless \
            --user-classes StressTestUser \
            --html=stress_report.html
        ;;

    spike)
        echo "Running Spike Test (sudden load)..."
        locust -f tests/test_performance.py \
            --host=$HOST \
            --users=1000 \
            --spawn-rate=100 \
            --run-time=2m \
            --headless \
            --user-classes SpikeTestUser \
            --html=spike_report.html
        ;;

    soak)
        echo "Running Soak Test (prolonged load)..."
        locust -f tests/test_performance.py \
            --host=$HOST \
            --users=50 \
            --spawn-rate=5 \
            --run-time=2h \
            --headless \
            --user-classes SoakTestUser \
            --html=soak_report.html
        ;;

    web)
        echo "Starting Locust Web UI..."
        echo "Open http://localhost:8089 in your browser"
        locust -f tests/test_performance.py --host=$HOST
        ;;

    *)
        echo "Unknown test type: $TEST_TYPE"
        echo "Available types: load, stress, spike, soak, web"
        exit 1
        ;;
esac

echo ""
echo "✓ Performance test completed!"
echo "Report saved to: ${TEST_TYPE}_report.html"
