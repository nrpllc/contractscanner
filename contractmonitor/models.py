from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Contract:
    title: str
    source: str  # which site it came from
    url: str
    agency: str = ""
    description: str = ""
    posted_date: str = ""
    due_date: str = ""
    contract_type: str = ""  # solicitation, award, intent, etc.
    amount: str = ""
    vendor: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def unique_id(self) -> str:
        """Stable ID for dedup across scans."""
        return f"{self.source}|{self.url}|{self.title}"

    def summary(self) -> str:
        lines = [
            f"[{self.source}] {self.title}",
            f"  Agency: {self.agency}",
            f"  Type: {self.contract_type}" if self.contract_type else "",
            f"  Posted: {self.posted_date}" if self.posted_date else "",
            f"  Due: {self.due_date}" if self.due_date else "",
            f"  Amount: {self.amount}" if self.amount else "",
            f"  Vendor: {self.vendor}" if self.vendor else "",
            f"  URL: {self.url}",
            f"  Description: {self.description[:200]}" if self.description else "",
        ]
        return "\n".join(line for line in lines if line)
