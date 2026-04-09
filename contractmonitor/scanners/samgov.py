"""
Scanner for SAM.gov — https://sam.gov/

Uses the SAM.gov Opportunities API for federal contracts
that may involve NYPD (DHS, DOJ grants and procurements).
Requires a free API key from https://api.data.gov/
"""

import logging

import httpx

from contractmonitor.models import Contract
from contractmonitor.scanners.base import BaseScanner

logger = logging.getLogger(__name__)

SAM_API_BASE = "https://api.sam.gov/opportunities/v2/search"


class SamGovScanner(BaseScanner):
    name = "SAM.gov"

    async def scan(self) -> list[Contract]:
        if not self.config.sam_api_key:
            logger.info("SAM.gov API key not configured — skipping")
            return []

        contracts = []
        keywords = [
            "NYPD",
            '"New York City Police Department"',
            '"NYC Police"',
        ]

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for keyword in keywords:
                found = await self._search(client, keyword)
                contracts.extend(found)

        # Dedup by URL
        seen = set()
        deduped = []
        for c in contracts:
            if c.url not in seen:
                seen.add(c.url)
                deduped.append(c)
        return deduped

    async def _search(
        self, client: httpx.AsyncClient, keyword: str
    ) -> list[Contract]:
        contracts = []
        try:
            params = {
                "api_key": self.config.sam_api_key,
                "q": keyword,
                "postedFrom": "",  # last 90 days by default
                "limit": "100",
                "offset": "0",
                "ptype": "o,k,p",  # opportunities: solicitation, presolicitation, etc.
            }

            resp = await client.get(SAM_API_BASE, params=params)

            if resp.status_code == 200:
                data = resp.json()
                opportunities = data.get("opportunitiesData", [])
                for opp in opportunities:
                    contract = self._parse_opportunity(opp)
                    if contract:
                        contracts.append(contract)
            elif resp.status_code == 403:
                logger.error("SAM.gov API key invalid or expired")
            else:
                logger.warning(f"SAM.gov returned {resp.status_code}")

        except Exception as e:
            logger.error(f"SAM.gov search failed for '{keyword}': {e}")

        return contracts

    def _parse_opportunity(self, opp: dict) -> Contract | None:
        try:
            title = opp.get("title", "")
            description = opp.get("description", "")
            notice_id = opp.get("noticeId", "")
            sol_number = opp.get("solicitationNumber", "")

            # Check if NYPD-related
            combined = f"{title} {description} {opp.get('organizationType', '')} {opp.get('fullParentPathName', '')}"
            if not self.is_nypd(combined):
                # Also check for NYC + police mentions
                if not ("new york" in combined.lower() and "police" in combined.lower()):
                    return None

            url = f"https://sam.gov/opp/{notice_id}/view" if notice_id else "https://sam.gov/"

            return Contract(
                title=title,
                source=self.name,
                url=url,
                agency=opp.get("fullParentPathName", ""),
                description=description[:500] if description else "",
                posted_date=opp.get("postedDate", ""),
                due_date=opp.get("responseDeadLine", ""),
                contract_type=opp.get("type", "Federal Opportunity"),
                extra={
                    "solicitation_number": sol_number,
                    "naics": opp.get("naicsCode", ""),
                    "set_aside": opp.get("typeOfSetAside", ""),
                },
            )
        except Exception as e:
            logger.debug(f"SAM.gov opportunity parse failed: {e}")
            return None
