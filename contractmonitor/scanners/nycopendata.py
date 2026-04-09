"""
Scanner for NYC Open Data — https://data.cityofnewyork.us/

Uses the Socrata Open Data API (SODA) to query procurement datasets.
"""

import logging

import httpx

from contractmonitor.models import Contract
from contractmonitor.scanners.base import BaseScanner

logger = logging.getLogger(__name__)

# Verified procurement dataset IDs on NYC Open Data
DATASETS = {
    "qyyg-4tf5": "Recent Contract Awards",
    "3khw-qi8f": "Current Solicitations",
    "nd82-bi9f": "Procurement By Industry",
    "tsak-vtv3": "Upcoming Contracts to be Awarded (CIP)",
    "6m3u-8rbh": "Upcoming Contracts to be Awarded (CAP)",
}

SOCRATA_BASE = "https://data.cityofnewyork.us/resource"

# Common agency field names across datasets
AGENCY_FIELDS = [
    "agency",
    "agency_name",
    "contracting_agency",
    "contracting_agency_name",
    "agency_acronym",
]


class NYCOpenDataScanner(BaseScanner):
    name = "NYCOpenData"

    async def scan(self) -> list[Contract]:
        contracts = []
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for dataset_id, dataset_name in DATASETS.items():
                found = await self._query_dataset(
                    client, dataset_id, dataset_name
                )
                contracts.extend(found)
        return contracts

    async def _query_dataset(
        self,
        client: httpx.AsyncClient,
        dataset_id: str,
        dataset_name: str,
    ) -> list[Contract]:
        contracts = []
        url = f"{SOCRATA_BASE}/{dataset_id}.json"

        for field in AGENCY_FIELDS:
            try:
                params = {
                    "$where": f"upper({field}) like '%POLICE%'",
                    "$limit": "200",
                    "$order": ":updated_at DESC",
                }
                resp = await client.get(url, params=params)

                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        logger.info(
                            f"NYCOpenData {dataset_name}: {len(data)} results "
                            f"(field: {field})"
                        )
                        for item in data:
                            contract = self._parse_record(
                                item, dataset_name, dataset_id, field
                            )
                            if contract:
                                contracts.append(contract)
                        break  # Found the right field
                elif resp.status_code == 400:
                    continue  # Field doesn't exist, try next
                else:
                    logger.warning(
                        f"NYCOpenData {dataset_id} returned {resp.status_code}"
                    )
                    break

            except Exception as e:
                logger.debug(
                    f"NYCOpenData query failed for {dataset_id}/{field}: {e}"
                )
                continue

        return contracts

    def _parse_record(
        self,
        item: dict,
        dataset_name: str,
        dataset_id: str,
        agency_field: str,
    ) -> Contract | None:
        try:
            agency = item.get(agency_field, "")
            if not self.is_nypd(agency):
                return None

            title = (
                item.get("contract_purpose", "")
                or item.get("purpose", "")
                or item.get("short_title", "")
                or item.get("description", "")
                or item.get("title", "")
                or item.get("service_description", "")
                or f"Contract in {dataset_name}"
            )

            contract_id = (
                item.get("contract_id", "")
                or item.get("contract_number", "")
                or item.get("document_id", "")
                or item.get("pin", "")
                or ""
            )

            vendor = (
                item.get("vendor_name", "")
                or item.get("vendor", "")
                or item.get("prime_vendor", "")
                or ""
            )

            amount = str(
                item.get("current_amount", "")
                or item.get("maximum_contract_amount", "")
                or item.get("contract_amount", "")
                or item.get("award_amount", "")
                or ""
            )

            start_date = (
                item.get("start_date", "")
                or item.get("registration_date", "")
                or item.get("award_date", "")
                or ""
            )

            record_url = f"https://data.cityofnewyork.us/d/{dataset_id}"

            return Contract(
                title=title,
                source=self.name,
                url=record_url,
                agency=agency,
                vendor=vendor,
                amount=amount,
                posted_date=str(start_date)[:10] if start_date else "",
                contract_type="Award",
                description=f"[{dataset_name}] {title}",
                extra={"dataset": dataset_id, "contract_id": contract_id},
            )

        except Exception as e:
            logger.debug(f"NYCOpenData record parse failed: {e}")
            return None
