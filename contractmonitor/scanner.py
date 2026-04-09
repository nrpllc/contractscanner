"""
Main orchestrator — runs all scanners, filters through LLM, dedup, and notifies.
"""

import asyncio
import logging
from datetime import datetime

from contractmonitor.config import Config
from contractmonitor.llm import analyze_contract
from contractmonitor.models import Contract
from contractmonitor.notify import print_notification, send_notification
from contractmonitor.scanners.checkbook import CheckbookScanner
from contractmonitor.scanners.cityrecord import CityRecordScanner
from contractmonitor.scanners.nycopendata import NYCOpenDataScanner
from contractmonitor.scanners.passport import PassportScanner
from contractmonitor.scanners.samgov import SamGovScanner
from contractmonitor.state import StateManager

logger = logging.getLogger(__name__)

ALL_SCANNERS = [
    CityRecordScanner,
    PassportScanner,
    CheckbookScanner,
    NYCOpenDataScanner,
    SamGovScanner,
]


async def run_scan(config: Config, state: StateManager) -> list[Contract]:
    """Run all scanners and return new NYPD contracts."""
    timestamp = datetime.now().isoformat()
    logger.info(f"Starting scan at {timestamp}")

    all_contracts: list[Contract] = []
    scanner_results: dict[str, list[Contract]] = {}

    # Run all scanners concurrently with a 90-second overall timeout
    scanners = [cls(config) for cls in ALL_SCANNERS]
    tasks = {
        asyncio.create_task(scanner.scan()): scanner
        for scanner in scanners
    }
    done, pending = await asyncio.wait(tasks.keys(), timeout=90)

    # Cancel any scanners that didn't finish in time
    for task in pending:
        scanner = tasks[task]
        logger.warning(f"{scanner.name} timed out after 90s — skipping")
        task.cancel()
        state.log_scan(scanner.name, 0, 0)

    for task in done:
        scanner = tasks[task]
        try:
            result = task.result()
        except Exception as e:
            logger.error(f"{scanner.name} failed: {e}")
            state.log_scan(scanner.name, 0, 0)
            continue

        logger.info(f"{scanner.name}: found {len(result)} potential contracts")
        scanner_results[scanner.name] = result

    # Combine all results
    for source, contracts in scanner_results.items():
        all_contracts.extend(contracts)

    # Run LLM analysis on contracts that passed keyword filter
    # and on ambiguous ones from non-NYPD agencies
    verified = []
    for contract in all_contracts:
        # If keyword match already strong, keep it
        combined_text = f"{contract.agency} {contract.title} {contract.description}"
        keyword_match = any(
            kw.upper() in combined_text.upper() for kw in config.agency_keywords
        )

        if keyword_match:
            verified.append(contract)
            continue

        # Use LLM for ambiguous cases
        llm_result = await analyze_contract(contract)
        if llm_result.get("is_nypd") is True and llm_result.get("confidence", 0) >= 0.6:
            contract.extra["llm_confidence"] = llm_result["confidence"]
            contract.extra["llm_reason"] = llm_result["reason"]
            verified.append(contract)
            logger.info(
                f"LLM confirmed NYPD contract: {contract.title} "
                f"(confidence: {llm_result['confidence']})"
            )

    # Filter out already-seen contracts
    new_contracts = state.filter_new(verified)

    # Log scan results
    for source, contracts in scanner_results.items():
        source_new = [c for c in new_contracts if c.source == source]
        state.log_scan(source, len(contracts), len(source_new))

    # Store new contracts
    if new_contracts:
        state.add_contracts(new_contracts)
        logger.info(f"Found {len(new_contracts)} NEW NYPD contracts")
    else:
        logger.info("No new NYPD contracts found")

    state.save()
    return new_contracts


async def scan_and_notify(config: Config, state: StateManager) -> None:
    """Run scan and send notifications for new contracts."""
    new_contracts = await run_scan(config, state)
    if new_contracts:
        send_notification(new_contracts, config)
