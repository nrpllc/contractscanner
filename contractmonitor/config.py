import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # SMTP
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    notify_to: str = os.getenv("NOTIFY_TO", "")
    notify_from: str = os.getenv("NOTIFY_FROM", "")

    # SAM.gov
    sam_api_key: str = os.getenv("SAM_API_KEY", "")

    # Scan interval
    scan_interval_minutes: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "30"))

    # Agency filter
    agency_keywords: list[str] = field(default_factory=lambda: [
        "NYPD",
        "New York City Police",
        "NYC Police Department",
        "Police Department",
        "N.Y.P.D.",
    ])

    # State file for dedup
    state_file: str = os.getenv(
        "STATE_FILE",
        os.path.join(os.path.dirname(__file__), "..", "seen_contracts.json"),
    )
