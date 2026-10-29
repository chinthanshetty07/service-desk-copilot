"""Deterministic checks that run before and around the model."""
from __future__ import annotations

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w])\+?\d[\d\s-]{8,}\d(?![\w])")

_P1 = re.compile(
    r"\b(outage|down for (?:everyone|all|the whole)|whole (?:floor|office|team)|all users|many users|"
    r"everyone in|clicked (?:a|the|on (?:a|the)) link|entered my password|stolen|lost my (?:laptop|phone)|"
    r"security incident|ransomware)\b",
    re.I,
)
_P2 = re.compile(
    r"\b(locked out|account (?:is )?locked|can'?t (?:log ?in|sign in|work|connect|access)|"
    r"cannot (?:log ?in|sign in|work|connect|access)|unable to (?:work|log ?in|sign in|connect|access)|urgent|blocked)\b",
    re.I,
)


def redact(text: str) -> tuple[str, int]:
    """Mask email addresses and phone numbers before text leaves the service. Returns (text, count)."""
    text, emails = _EMAIL.subn("[EMAIL]", text)
    text, phones = _PHONE.subn("[PHONE]", text)
    return text, emails + phones


def priority(text: str) -> str:
    """Rule-based priority matching the service desk policy (KB-014), so SLAs never depend on the model."""
    if _P1.search(text):
        return "P1"
    if _P2.search(text):
        return "P2"
    return "P3"


AUTOMATION_REQUIREMENTS = {
    "password_reset": "Identity verification via the registered MFA method",
    "account_unlock": "Identity verification; failures must come from the user's own devices",
    "access_request": "Approval from the resource owner or manager",
    "software_request": "App must be in the approved catalogue",
}
