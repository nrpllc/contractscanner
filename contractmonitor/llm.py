"""
Local LLM integration for analyzing whether scraped content relates to NYPD contracts.

Supports Ollama (default), LM Studio, or any OpenAI-compatible local endpoint.
Configure via LLM_BASE_URL and LLM_MODEL in .env.
"""

import json
import logging
import os

import httpx

from contractmonitor.models import Contract

logger = logging.getLogger(__name__)

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3")

SYSTEM_PROMPT = """You are a contract analysis assistant. Your job is to determine whether a given contract or procurement notice is related to the New York City Police Department (NYPD).

Analyze the provided contract information and respond with a JSON object:
{
  "is_nypd": true/false,
  "confidence": 0.0-1.0,
  "reason": "brief explanation"
}

Consider a contract NYPD-related if:
- The contracting agency is NYPD, NYC Police Department, or similar
- The contract is for police equipment, law enforcement technology, public safety services
- The vendor/purpose explicitly mentions NYPD or police operations
- The contract is from another agency (like DCAS, DDC, DoITT) but is serving NYPD

Be thorough — some contracts are for NYPD but posted by other agencies (e.g., DCAS buying vehicles for NYPD, DDC building a precinct house).

Respond ONLY with the JSON object, no other text."""


async def analyze_contract(contract: Contract) -> dict:
    """Ask local LLM whether this contract is NYPD-related."""
    prompt = f"""Analyze this contract/procurement notice:

Title: {contract.title}
Agency: {contract.agency}
Source: {contract.source}
Type: {contract.contract_type}
Description: {contract.description}
Vendor: {contract.vendor}
Amount: {contract.amount}
URL: {contract.url}
"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            # Try Ollama API first
            resp = await client.post(
                f"{LLM_BASE_URL}/api/generate",
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": False,
                    "format": "json",
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                response_text = data.get("response", "")
                return _parse_llm_response(response_text)

            # Fallback: try OpenAI-compatible /v1/chat/completions
            resp = await client.post(
                f"{LLM_BASE_URL}/v1/chat/completions",
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return _parse_llm_response(content)

            logger.warning(f"LLM request failed with status {resp.status_code}")

    except httpx.ConnectError:
        logger.warning(
            f"Cannot connect to local LLM at {LLM_BASE_URL} — "
            "falling back to keyword matching. "
            "Start Ollama or set LLM_BASE_URL in .env"
        )
    except Exception as e:
        logger.warning(f"LLM analysis failed: {e}")

    # Fallback: return unknown so keyword match is used
    return {"is_nypd": None, "confidence": 0.0, "reason": "LLM unavailable"}


def _parse_llm_response(text: str) -> dict:
    """Parse the JSON response from the LLM."""
    try:
        # Try to extract JSON from the response
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
        return {
            "is_nypd": bool(result.get("is_nypd", False)),
            "confidence": float(result.get("confidence", 0.0)),
            "reason": str(result.get("reason", "")),
        }
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.debug(f"Failed to parse LLM response: {e}")
        # Try to infer from text
        text_lower = text.lower()
        if '"is_nypd": true' in text_lower or '"is_nypd":true' in text_lower:
            return {"is_nypd": True, "confidence": 0.7, "reason": "Parsed from text"}
        return {"is_nypd": None, "confidence": 0.0, "reason": "Parse failed"}
