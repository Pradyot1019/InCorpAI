"""Controlled vocabulary for metadata filters.

This is the single source of truth for jurisdictions / entity types / phases.
The frontend fetches it from GET /api/taxonomy so it never hard-codes options.
"""

from __future__ import annotations

import re

JURISDICTIONS: list[dict] = [
    {
        "code": "IN",
        "name": "India",
        "regulators": ["MCA", "DPIIT", "CBDT", "MeitY"],
        "entity_types": ["Pvt Ltd", "LLP", "OPC"],
        "summary": "Companies Act 2013, SPICe+ filing, Startup India, DPDP Act 2023",
    },
    {
        "code": "US-DE",
        "name": "United States — Delaware",
        "regulators": ["DE Division of Corporations", "IRS", "SEC"],
        "entity_types": ["C-Corp", "LLC"],
        "summary": "DGCL, Certificate of Incorporation, EIN, 83(b), franchise tax",
    },
    {
        "code": "EU",
        "name": "European Union",
        "regulators": ["EDPB", "National DPAs"],
        "entity_types": ["Any"],
        "summary": "GDPR obligations for startups processing EU personal data",
    },
]

ENTITY_TYPE_LABELS: dict[str, str] = {
    "Pvt Ltd": "Private Limited Company",
    "LLP": "Limited Liability Partnership",
    "OPC": "One Person Company",
    "C-Corp": "C-Corporation",
    "LLC": "Limited Liability Company",
    "Any": "Any entity type",
}

COMPLIANCE_PHASES: list[str] = [
    "Pre-Incorporation",
    "Incorporation",
    "Post-Incorporation",
    "Ongoing Compliance",
    "Data Privacy",
]

JURISDICTION_CODES = {j["code"] for j in JURISDICTIONS}

# --- Query-side filter extraction ----------------------------------------------
# If the user's text explicitly names a jurisdiction / entity, it overrides the UI selection.
# Ordered: more specific patterns first.
_JURISDICTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(delaware|dgcl|de\s+c-?corp|franchise\s+tax)\b", re.IGNORECASE), "US-DE"),
    (re.compile(r"\b(gdpr|european\s+union|\beu\b|edpb)\b", re.IGNORECASE), "EU"),
    (re.compile(r"\b(india|indian|mca|spice\+?|dpiit|startup\s+india|dpdp|roc)\b", re.IGNORECASE), "IN"),
]

_ENTITY_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(llp|limited\s+liability\s+partnership)\b", re.IGNORECASE), "LLP"),
    (re.compile(r"\b(opc|one\s+person\s+company)\b", re.IGNORECASE), "OPC"),
    (re.compile(r"\b(llc|limited\s+liability\s+company)\b", re.IGNORECASE), "LLC"),
    (re.compile(r"\b(c-?corp(oration)?)\b", re.IGNORECASE), "C-Corp"),
    (re.compile(r"\b(pvt\.?\s*ltd|private\s+limited)\b", re.IGNORECASE), "Pvt Ltd"),
]


def detect_jurisdiction(text: str) -> str | None:
    for pattern, code in _JURISDICTION_PATTERNS:
        if pattern.search(text):
            return code
    return None


def detect_entity_type(text: str) -> str | None:
    for pattern, entity in _ENTITY_PATTERNS:
        if pattern.search(text):
            return entity
    return None


def entity_valid_for(jurisdiction: str, entity_type: str) -> bool:
    for j in JURISDICTIONS:
        if j["code"] == jurisdiction:
            return entity_type in j["entity_types"]
    return False


# Starter prompts the UI shows in its empty state, per jurisdiction.
SUGGESTED_PROMPTS: dict[str, list[str]] = {
    "IN": [
        "Walk me through incorporating a Private Limited company with SPICe+",
        "What must we file in the first 180 days after incorporation?",
        "Are we eligible for DPIIT startup recognition, and how do we apply?",
        "What does the DPDP Act require if we suffer a data breach?",
    ],
    "US-DE": [
        "What are the steps to form a Delaware C-Corp?",
        "When is the 83(b) election due and why does it matter?",
        "How do I lower a large Delaware franchise tax bill?",
        "What federal tax forms does a foreign-owned C-Corp file?",
    ],
    "EU": [
        "Does GDPR apply to a non-EU startup with EU users?",
        "Give me a GDPR readiness checklist for launch",
        "How fast do we have to report a personal data breach?",
        "How can we transfer EU personal data to India or the US?",
    ],
}
