"""
Database migration utilities
Auto-runs Alembic migrations at application startup
"""
import os
import sys
import logging
from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)

def run_migrations() -> None:
    """
    Run Alembic migrations automatically at startup
    Upgrades database to the latest revision
    """
    try:
        # Get the project root directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))

        # Path to alembic.ini
        alembic_ini_path = os.path.join(project_root, 'alembic.ini')

        if not os.path.exists(alembic_ini_path):
            logger.warning(f"Alembic config not found: {alembic_ini_path}")
            return

        logger.info("Running database migrations...")

        # Create Alembic config
        alembic_cfg = Config(alembic_ini_path)

        # Set the script location
        alembic_cfg.set_main_option('script_location', os.path.join(project_root, 'alembic'))

        # Run migrations
        command.upgrade(alembic_cfg, "head")

        logger.info("Database migrations completed successfully")

    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        # Don't raise - allow app to start even if migrations fail
        # (useful for local development without database)

def create_migration(message: str) -> None:
    """
    Create a new Alembic migration
    Args:
        message: Description of the migration
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        alembic_ini_path = os.path.join(project_root, 'alembic.ini')

        if not os.path.exists(alembic_ini_path):
            logger.error(f"Alembic config not found: {alembic_ini_path}")
            return

        logger.info(f"Creating migration: {message}")

        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option('script_location', os.path.join(project_root, 'alembic'))

        # Auto-generate migration
        command.revision(alembic_cfg, message=message, autogenerate=True)

        logger.info("Migration created successfully")

    except Exception as e:
        logger.error(f"Error creating migration: {e}")
        raise
