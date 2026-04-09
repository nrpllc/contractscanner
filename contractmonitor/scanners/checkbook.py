"""
Scanner for Checkbook NYC — https://www.checkbooknyc.com/

Uses the Checkbook NYC API (POST XML to /api) for awarded/registered contracts.
"""

import logging

import httpx
from bs4 import BeautifulSoup

from contractmonitor.models import Contract
from contractmonitor.scanners.base import BaseScanner

logger = logging.getLogger(__name__)

CHECKBOOK_API = "https://www.checkbooknyc.com/api"


class CheckbookScanner(BaseScanner):
    name = "CheckbookNYC"

    async def scan(self) -> list[Contract]:
        contracts = []
        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                for status in ["registered", "pending"]:
                    found = await self._query(client, status)
                    contracts.extend(found)
        except Exception as e:
            logger.error(f"Checkbook scan failed: {e}")
        return contracts

    async def _query(
        self, client: httpx.AsyncClient, status: str
    ) -> list[Contract]:
        contracts = []

        request_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<request>
    <type_of_data>Contracts</type_of_data>
    <records_from>1</records_from>
    <max_records>100</max_records>
    <search_criteria>
        <criteria>
            <name>status</name>
            <type>value</type>
            <value>{status}</value>
        </criteria>
        <criteria>
            <name>category</name>
            <type>value</type>
            <value>expense</value>
        </criteria>
    </search_criteria>
    <response_columns>
        <column>prime_contract_id</column>
        <column>prime_contracting_agency</column>
        <column>prime_vendor</column>
        <column>prime_contract_purpose</column>
        <column>prime_contract_current_amount</column>
        <column>prime_contract_original_amount</column>
        <column>prime_contract_start_date</column>
        <column>prime_contract_end_date</column>
        <column>prime_contract_registration_date</column>
        <column>prime_contract_type</column>
        <column>prime_contract_award_method</column>
        <column>prime_contract_pin</column>
    </response_columns>
</request>"""

        try:
            resp = await client.post(
                CHECKBOOK_API,
                content=request_xml,
                headers={"Content-Type": "application/xml"},
            )

            if resp.status_code == 200:
                found = self._parse_response(resp.text, status)
                logger.info(
                    f"CheckbookNYC ({status}): {len(found)} NYPD contracts"
                )
                contracts.extend(found)
            else:
                logger.warning(
                    f"Checkbook API ({status}) returned {resp.status_code}"
                )

        except Exception as e:
            logger.error(f"Checkbook query failed ({status}): {e}")

        return contracts

    def _parse_response(self, xml_text: str, status: str) -> list[Contract]:
        contracts = []
        try:
            soup = BeautifulSoup(xml_text, "html.parser")
            for record in soup.find_all("record"):
                agency = self._xml_text(record, "prime_contracting_agency")
                if not self.is_nypd(agency):
                    continue

                contract_id = self._xml_text(record, "prime_contract_id")
                vendor = self._xml_text(record, "prime_vendor")
                purpose = self._xml_text(record, "prime_contract_purpose")
                amount = self._xml_text(record, "prime_contract_current_amount")
                start_date = self._xml_text(record, "prime_contract_start_date")
                reg_date = self._xml_text(record, "prime_contract_registration_date")
                ctype = self._xml_text(record, "prime_contract_type")
                award_method = self._xml_text(record, "prime_contract_award_method")
                pin = self._xml_text(record, "prime_contract_pin")

                url = f"https://www.checkbooknyc.com/contracts_landing/status/A/yeartype/B/year/125?expandBottomContURL=/contract_details/agency/057/agtype/e/cid/{contract_id}" if contract_id else "https://www.checkbooknyc.com/"

                contracts.append(
                    Contract(
                        title=purpose or f"Contract {contract_id}",
                        source=self.name,
                        url=url,
                        agency=agency,
                        vendor=vendor,
                        amount=amount,
                        posted_date=reg_date or start_date,
                        contract_type=f"{ctype} ({status})" if ctype else status.title(),
                        description=purpose,
                        extra={
                            "contract_id": contract_id,
                            "award_method": award_method,
                            "pin": pin,
                        },
                    )
                )
        except Exception as e:
            logger.error(f"Checkbook XML parse failed: {e}")

        return contracts

    def _xml_text(self, element, tag: str) -> str:
        el = element.find(tag)
        return el.get_text(strip=True) if el else ""
