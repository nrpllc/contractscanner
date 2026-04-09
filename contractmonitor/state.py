"""
State management — tracks seen contracts for dedup and persists scan results.
"""

import json
import logging
import os
from datetime import datetime

from contractmonitor.models import Contract

logger = logging.getLogger(__name__)


class StateManager:
    def __init__(self, state_file: str):
        self.state_file = os.path.abspath(state_file)
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        return {"seen": {}, "contracts": [], "scans": []}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.data, f, indent=2, default=str)

    def is_new(self, contract: Contract) -> bool:
        return contract.unique_id not in self.data["seen"]

    def mark_seen(self, contract: Contract) -> None:
        self.data["seen"][contract.unique_id] = datetime.now().isoformat()

    def filter_new(self, contracts: list[Contract]) -> list[Contract]:
        new = [c for c in contracts if self.is_new(c)]
        for c in new:
            self.mark_seen(c)
        return new

    def add_contracts(self, contracts: list[Contract]) -> None:
        for c in contracts:
            self.data["contracts"].append({
                "title": c.title,
                "source": c.source,
                "url": c.url,
                "agency": c.agency,
                "description": c.description,
                "posted_date": c.posted_date,
                "due_date": c.due_date,
                "contract_type": c.contract_type,
                "amount": c.amount,
                "vendor": c.vendor,
                "found_at": datetime.now().isoformat(),
                "extra": c.extra,
            })
        # Keep last 1000 contracts
        self.data["contracts"] = self.data["contracts"][-1000:]

    def log_scan(self, source: str, count: int, new_count: int) -> None:
        self.data["scans"].append({
            "source": source,
            "total_found": count,
            "new_found": new_count,
            "timestamp": datetime.now().isoformat(),
        })
        # Keep last 500 scan logs
        self.data["scans"] = self.data["scans"][-500:]

    def get_all_contracts(self) -> list[dict]:
        return self.data.get("contracts", [])

    def get_scan_history(self) -> list[dict]:
        return self.data.get("scans", [])
