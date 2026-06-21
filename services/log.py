"""
Logging configuration
"""

import logging


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """
    Configure process-wide logging for command-line runs.
    """
    level = logging.WARNING if quiet else (
        logging.DEBUG if verbose else logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)-7s %(name)s: %(message)s',
    )
