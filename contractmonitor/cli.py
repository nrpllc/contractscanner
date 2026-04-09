"""
CLI entry point for the NYPD Contract Monitor.
"""

import argparse
import asyncio
import logging
import sys
import time

from contractmonitor.config import Config
from contractmonitor.scanner import scan_and_notify
from contractmonitor.state import StateManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Monitor NYC contract sites for NYPD contracts"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scan and exit",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Scan interval in minutes (default: 30)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the web dashboard server",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8200,
        help="Web dashboard port (default: 8200)",
    )
    args = parser.parse_args()

    config = Config()
    if args.interval:
        config.scan_interval_minutes = args.interval

    state = StateManager(config.state_file)

    if args.serve:
        _run_server(config, state, args.port)
    elif args.once:
        asyncio.run(scan_and_notify(config, state))
    else:
        _run_loop(config, state)


def _run_loop(config: Config, state: StateManager):
    """Run scans on a recurring interval."""
    interval = config.scan_interval_minutes
    logger.info(
        f"NYPD Contract Monitor started — scanning every {interval} minutes"
    )
    logger.info("Sources: CityRecord, PASSPort, CheckbookNYC, NYCOpenData, SAM.gov")
    logger.info("Press Ctrl+C to stop")

    while True:
        try:
            asyncio.run(scan_and_notify(config, state))
        except KeyboardInterrupt:
            logger.info("Shutting down")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Scan cycle failed: {e}")

        logger.info(f"Next scan in {interval} minutes...")
        try:
            time.sleep(interval * 60)
        except KeyboardInterrupt:
            logger.info("Shutting down")
            sys.exit(0)


def _run_server(config: Config, state: StateManager, port: int):
    """Start the web dashboard with background scanning."""
    from contractmonitor.server import create_app

    app = create_app(config, state)

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
