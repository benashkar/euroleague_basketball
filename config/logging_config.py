"""
=============================================================================
LOGGING CONFIGURATION
=============================================================================

PURPOSE:
    Centralized logging configuration that writes to both console AND files.
    This keeps a history of all scrape runs for debugging.

HOW TO USE:
    Instead of setting up logging in each script, import this:

        from config.logging_config import setup_logging
        logger = setup_logging('daily_scraper')

    This creates log files in the logs/ directory:
        - logs/daily_scraper_2024-01-15.log
        - logs/hometown_lookup_2024-01-15.log

    Logs rotate daily, keeping the last 7 days.

WHY USE FILE LOGGING:
    1. Keep history of past runs for debugging
    2. Track errors over time
    3. Verify automated runs completed successfully
    4. Audit trail for data changes
"""

import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


def setup_logging(script_name, log_level=logging.INFO):
    """
    Set up logging to both console and file.

    PARAMETERS:
        script_name (str): Name of the script (used in log filename)
                          Example: 'daily_scraper', 'hometown_lookup'
        log_level: Logging level (default: INFO)
                   Options: DEBUG, INFO, WARNING, ERROR, CRITICAL

    RETURNS:
        logging.Logger: Configured logger instance

    EXAMPLE:
        >>> logger = setup_logging('daily_scraper')
        >>> logger.info("Starting scrape...")
        2024-01-15 10:30:00 - INFO - Starting scrape...

    LOG FILES:
        Saved to: logs/<script_name>_YYYY-MM-DD.log
        Rotates: Daily at midnight
        Keeps: Last 7 days of logs
    """
    # Create logs directory if it doesn't exist
    # We use the parent directory of config/ (project root)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(project_root, 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    # Create logger
    logger = logging.getLogger(script_name)
    logger.setLevel(log_level)

    # Clear any existing handlers (prevents duplicate logs)
    logger.handlers = []

    # Define log format
    # Format: timestamp - script name - level - message
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # =========================================================================
    # Console Handler - outputs to terminal
    # =========================================================================
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # =========================================================================
    # File Handler - outputs to dated log file
    # =========================================================================
    # Generate log filename with date
    today = datetime.now().strftime('%Y-%m-%d')
    log_filename = os.path.join(logs_dir, f'{script_name}_{today}.log')

    # TimedRotatingFileHandler rotates logs daily
    # - when='midnight': Rotate at midnight
    # - interval=1: Every 1 day
    # - backupCount=7: Keep 7 days of logs
    file_handler = TimedRotatingFileHandler(
        log_filename,
        when='midnight',
        interval=1,
        backupCount=7,  # Keep last 7 days
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Log that we started
    logger.info(f"Logging initialized for {script_name}")
    logger.info(f"Log file: {log_filename}")

    return logger


def get_logger(name):
    """
    Get an existing logger by name.

    Use this when you need to get a logger that was already set up.

    PARAMETERS:
        name (str): Logger name (same as used in setup_logging)

    RETURNS:
        logging.Logger: The logger instance
    """
    return logging.getLogger(name)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def log_scrape_start(logger, mode='all'):
    """
    Log a standard scrape start message.

    PARAMETERS:
        logger: The logger instance
        mode: The scraping mode (all, recent, today)
    """
    logger.info("=" * 60)
    logger.info(f"SCRAPE STARTED - Mode: {mode.upper()}")
    logger.info("=" * 60)


def log_scrape_end(logger, stats):
    """
    Log a standard scrape completion message with statistics.

    PARAMETERS:
        logger: The logger instance
        stats (dict): Statistics about the scrape
                      Example: {'clubs': 18, 'players': 100, 'games': 200}
    """
    logger.info("=" * 60)
    logger.info("SCRAPE COMPLETED")
    logger.info("=" * 60)
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")


def log_error(logger, error, context=""):
    """
    Log an error with optional context.

    PARAMETERS:
        logger: The logger instance
        error: The error/exception
        context: Additional context about what was happening
    """
    if context:
        logger.error(f"{context}: {error}")
    else:
        logger.error(str(error))


# =============================================================================
# EXAMPLE USAGE
# =============================================================================
if __name__ == '__main__':
    # Demo the logging setup
    logger = setup_logging('test_logging')

    logger.debug("This is a DEBUG message (won't show by default)")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")

    # Demo the convenience functions
    log_scrape_start(logger, mode='recent')
    log_scrape_end(logger, {'clubs': 18, 'players': 100})
