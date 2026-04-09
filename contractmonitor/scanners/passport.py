"""
Scanner for NYC PASSPort — https://passport.cityofnewyork.us/

PASSPort is the City's primary procurement system. It uses dynamic JavaScript
rendering (Oracle-based), so we need Playwright for browser automation.
"""

import logging

from contractmonitor.models import Contract
from contractmonitor.scanners.base import BaseScanner

logger = logging.getLogger(__name__)

PASSPORT_URL = "https://passport.cityofnewyork.us/page.aspx/en/rfp/request_browse_public"


class PassportScanner(BaseScanner):
    name = "PASSPort"

    async def scan(self) -> list[Contract]:
        contracts = []
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(PASSPORT_URL, wait_until="domcontentloaded", timeout=30000)
                # Give the JS app time to render, but don't wait forever
                await page.wait_for_timeout(5000)

                # PASSPort has an agency filter — select NYPD
                await self._select_nypd_filter(page)

                # Wait for results to load
                await page.wait_for_timeout(3000)

                # Parse the results table
                contracts = await self._parse_results(page)

                # Check for pagination
                while await self._has_next_page(page):
                    await self._go_next_page(page)
                    await page.wait_for_timeout(2000)
                    page_contracts = await self._parse_results(page)
                    contracts.extend(page_contracts)

                await browser.close()

        except ImportError:
            logger.error(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )
        except Exception as e:
            logger.error(f"PASSPort scan failed: {e}")

        return contracts

    async def _select_nypd_filter(self, page) -> None:
        """Try to filter by NYPD in the agency dropdown."""
        try:
            # Look for agency filter controls
            selectors = [
                "select[name*='agency']",
                "select[name*='Agency']",
                "#agency-filter",
                "[data-field='agency'] select",
                "select.agency-select",
            ]
            for sel in selectors:
                element = await page.query_selector(sel)
                if element:
                    await element.select_option(label="Police Department (NYPD)")
                    logger.info("Selected NYPD filter in PASSPort")
                    return

            # If no dropdown, try search/filter input
            search_selectors = [
                "input[name*='agency']",
                "input[placeholder*='agency']",
                "input[placeholder*='Agency']",
                ".filter-input",
            ]
            for sel in search_selectors:
                element = await page.query_selector(sel)
                if element:
                    await element.fill("NYPD")
                    await page.keyboard.press("Enter")
                    logger.info("Searched NYPD in PASSPort filter")
                    return

            logger.warning("Could not find agency filter in PASSPort — will scan all and filter locally")

        except Exception as e:
            logger.warning(f"PASSPort filter selection failed: {e}")

    async def _parse_results(self, page) -> list[Contract]:
        """Parse the solicitation results table."""
        contracts = []
        try:
            # Try common table/list selectors
            rows = await page.query_selector_all(
                "table tbody tr, .rfp-item, .solicitation-row, .result-row"
            )
            for row in rows:
                text = await row.inner_text()
                # Only keep if it mentions NYPD (in case filter didn't work)
                if not self.is_nypd(text):
                    continue

                cells = await row.query_selector_all("td")
                link = await row.query_selector("a[href]")

                title = ""
                url = PASSPORT_URL
                if link:
                    title = (await link.inner_text()).strip()
                    href = await link.get_attribute("href")
                    if href:
                        if href.startswith("http"):
                            url = href
                        else:
                            url = f"https://passport.cityofnewyork.us{href}"
                elif cells:
                    title = (await cells[0].inner_text()).strip()

                if not title:
                    continue

                # Extract other fields from cells
                posted_date = ""
                due_date = ""
                contract_type = ""
                if len(cells) >= 3:
                    posted_date = (await cells[-2].inner_text()).strip()
                    due_date = (await cells[-1].inner_text()).strip()

                contracts.append(
                    Contract(
                        title=title,
                        source=self.name,
                        url=url,
                        agency="NYPD",
                        posted_date=posted_date,
                        due_date=due_date,
                        contract_type="Solicitation",
                    )
                )

        except Exception as e:
            logger.error(f"PASSPort results parsing failed: {e}")

        return contracts

    async def _has_next_page(self, page) -> bool:
        """Check if there's a next page button that's enabled."""
        try:
            next_btn = await page.query_selector(
                "a.next-page:not(.disabled), button.next:not([disabled]), "
                "[aria-label='Next page']:not([disabled])"
            )
            return next_btn is not None
        except Exception:
            return False

    async def _go_next_page(self, page) -> None:
        """Click the next page button."""
        try:
            next_btn = await page.query_selector(
                "a.next-page, button.next, [aria-label='Next page']"
            )
            if next_btn:
                await next_btn.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            logger.warning(f"PASSPort pagination failed: {e}")
