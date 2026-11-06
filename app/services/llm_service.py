import json
import re

import httpx

from app.core.config import get_settings
from app.schemas.matching import ParsedConstraints
from app.services.maps_service import NAIROBI_PLACES
from app.utils.helpers import normalize_name

SYSTEM_PROMPT = """You extract shopping constraints from Kenyan English queries.
Return JSON only with keys:
product (string, the item they want),
max_price_kes (number or null),
target_price_kes (number or null),
location (string or null, neighborhood/area),
extras (array of short strings).
Interpret "bob", "ksh", "kes", "shillings" as Kenyan shillings.
"under 300", "below 300", "max 300" means max_price_kes=300.
"around 259" means target_price_kes=259.
"""


def parse_query(query: str) -> ParsedConstraints:
    provider = get_settings().llm_provider
    if provider:
        parsed = _parse_with_llm(query, provider)
        if parsed:
            return parsed
    return _parse_offline(query)


def _parse_offline(query: str) -> ParsedConstraints:
    text = query.strip()
    lowered = text.lower()

    max_price = _first_number(
        lowered,
        r"(?:under|below|less than|max(?:imum)?|upto|up to|<=)\s*(\d+(?:\.\d+)?)"
        r"|(\d+(?:\.\d+)?)\s*(?:bob|ksh|kes|shillings?)?\s*(?:and below|max)",
    )
    target_price = None
    around = _first_number(lowered, r"(?:around|about|approx(?:imately)?|~)\s*(\d+(?:\.\d+)?)")
    if around is not None:
        target_price = around
    if max_price is None:
        bare = _first_number(lowered, r"(\d+(?:\.\d+)?)\s*(?:bob|ksh|kes|shillings?)")
        if bare is not None and around is None:
            max_price = bare

    location = None
    near_match = re.search(r"(?:near|in|around|at)\s+([a-z][a-z\s]{1,40})$", lowered)
    if near_match:
        candidate = near_match.group(1).strip()
        candidate = re.sub(r"\b(please|now|asap|today)\b", "", candidate).strip()
        location = candidate.title() if candidate else None
    if location is None:
        for name in NAIROBI_PLACES:
            if name in lowered:
                location = name.title()
                break

    product = lowered
    product = re.sub(r"\bi need\b|\bi want\b|\blooking for\b|\bfind me\b|\bget me\b", " ", product)
    product = re.sub(r"\b(under|below|less than|around|about|near|in|at)\b.*", " ", product)
    product = re.sub(r"\d+(?:\.\d+)?\s*(bob|ksh|kes|shillings?)?", " ", product)
    product = normalize_name(product) or normalize_name(text)

    extras: list[str] = []
    if "now" in lowered or "asap" in lowered or "right now" in lowered:
        extras.append("urgent")

    return ParsedConstraints(
        product=product,
        max_price_kes=max_price,
        target_price_kes=target_price,
        location=location,
        extras=extras,
        parser="offline",
    )


def _first_number(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text)
    if not match:
        return None
    for group in match.groups():
        if group:
            return float(group)
    return None


def _parse_with_llm(query: str, provider: str) -> ParsedConstraints | None:
    try:
        if provider == "anthropic":
            raw = _call_anthropic(query)
        else:
            raw = _call_openai_compatible(query, provider)
        data = json.loads(raw)
        return ParsedConstraints(
            product=str(data.get("product") or query).strip(),
            max_price_kes=_as_float(data.get("max_price_kes")),
            target_price_kes=_as_float(data.get("target_price_kes")),
            location=(str(data["location"]).strip() if data.get("location") else None),
            extras=list(data.get("extras") or []),
            parser=provider,
        )
    except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError, KeyError):
        return None


def _as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _call_openai_compatible(query: str, provider: str) -> str:
    settings = get_settings()
    if provider == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        api_key = settings.groq_api_key
        model = "llama-3.1-8b-instant"
    else:
        url = "https://api.openai.com/v1/chat/completions"
        api_key = settings.openai_api_key
        model = "gpt-4o-mini"

    response = httpx.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
        },
        timeout=20.0,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _call_anthropic(query: str) -> str:
    settings = get_settings()
    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-3-haiku-20240307",
            "max_tokens": 300,
            "temperature": 0,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": query}],
        },
        timeout=20.0,
    )
    response.raise_for_status()
    chunks = response.json()["content"]
    return "".join(part.get("text", "") for part in chunks)
