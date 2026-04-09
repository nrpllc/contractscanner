"""
Scanner for the City Record Online (CROL) via NYC Open Data.

The City Record is the official journal of the City of New York.
All procurement notices must be published here by law.

The full CROL dataset is published as Socrata dataset dg92-zbpx,
which is much more reliable than scraping the CROL website.
"""

import logging
from datetime import datetime, timedelta

import httpx

from contractmonitor.models import Contract
from contractmonitor.scanners.base import BaseScanner

logger = logging.getLogger(__name__)

# CROL dataset on NYC Open Data
CROL_DATASET = "dg92-zbpx"
CROL_API = f"https://data.cityofnewyork.us/resource/{CROL_DATASET}.json"


class CityRecordScanner(BaseScanner):
    name = "CityRecord"

    async def scan(self) -> list[Contract]:
        contracts = []
        today = datetime.now()
        from_date = (today - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00")

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                # Query for NYPD/Police Department notices
                for keyword in ["Police", "NYPD"]:
                    params = {
                        "$where": (
                            f"agency_name like '%{keyword}%' "
                            f"AND start_date > '{from_date}'"
                        ),
                        "$limit": "200",
                        "$order": "start_date DESC",
                    }
                    resp = await client.get(CROL_API, params=params)

                    if resp.status_code == 200:
                        data = resp.json()
                        logger.info(
                            f"CityRecord: {len(data)} results for '{keyword}'"
                        )
                        for item in data:
                            contract = self._parse_record(item)
                            if contract:
                                contracts.append(contract)
                    else:
                        logger.warning(
                            f"CityRecord API returned {resp.status_code} "
                            f"for '{keyword}'"
                        )

        except Exception as e:
            logger.error(f"CityRecord scan failed: {e}")

        # Dedup by request_id or URL
        seen = set()
        deduped = []
        for c in contracts:
            key = c.extra.get("request_id", c.url)
            if key not in seen:
                seen.add(key)
                deduped.append(c)
        return deduped

    def _parse_record(self, item: dict) -> Contract | None:
        try:
            agency = item.get("agency_name", "")
            if not self.is_nypd(agency):
                return None

            title = (
                item.get("short_title", "")
                or item.get("type_of_notice_description", "")
                or "City Record Notice"
            )

            request_id = item.get("request_id", "")
            notice_type = item.get("type_of_notice_description", "")
            category = item.get("category_description", "")
            vendor = item.get("vendor_name", "")
            amount = item.get("contract_amount", "")
            pin = item.get("pin", "")
            start_date = item.get("start_date", "")
            due_date = item.get("due_date", "")
            selection_method = item.get("selection_method_description", "")
            doc_links = item.get("document_links", "")

            url = (
                f"https://a856-cityrecord.nyc.gov/RequestDetail/{request_id}"
                if request_id
                else "https://a856-cityrecord.nyc.gov/"
            )

            description_parts = [
                f"Notice Type: {notice_type}" if notice_type else "",
                f"Category: {category}" if category else "",
                f"Selection Method: {selection_method}" if selection_method else "",
                f"PIN: {pin}" if pin else "",
            ]
            description = " | ".join(p for p in description_parts if p)

            return Contract(
                title=title,
                source=self.name,
                url=url,
                agency=agency,
                description=description,
                posted_date=str(start_date)[:10] if start_date else "",
                due_date=str(due_date)[:10] if due_date else "",
                contract_type=notice_type or "Notice",
                amount=str(amount) if amount else "",
                vendor=vendor,
                extra={
                    "request_id": request_id,
                    "pin": pin,
                    "category": category,
                    "document_links": doc_links,
                },
            )
        except Exception as e:
            logger.debug(f"Failed to parse CROL record: {e}")
            return None
