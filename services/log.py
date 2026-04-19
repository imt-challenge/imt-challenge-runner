"""
Logging configuration
"""

import logging


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    level = logging.WARNING if quiet else (logging.DEBUG if verbose else logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)-7s %(name)s: %(message)s',
    )
