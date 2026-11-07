import re

from app.schemas.matching import ParsedConstraints
from app.utils.helpers import normalize_name
from app.utils.kenya import KENYAN_COUNTIES, canonical_county

_INTENT = re.compile(
    r"\b(?:i need|i want|i am looking for|i'm looking for|looking for|"
    r"find me|get me|buy me|show me)\b",
    re.IGNORECASE,
)
_PRICE_CLAUSE = re.compile(
    r"\b(?:under|below|less than|maximum|max|up to|upto|around|about|"
    r"approximately|approx)\s*(?:kshs?|kes|bob|shillings?)?\s*\d+(?:\.\d+)?"
    r"\s*(?:kshs?|kes|bob|shillings?)?"
    r"|\d+(?:\.\d+)?\s*(?:kshs?|kes|bob|shillings?)\b"
    r"|\b\d+(?:\.\d+)?\s*(?:and below|max)\b",
    re.IGNORECASE,
)
_LOCATION_CLAUSE = re.compile(
    r"\b(?:near|in|around|at)\s+([a-z][a-z\s'-]{0,50}?)"
    r"(?=\s+(?:near|in|at|under|below|less than|max|maximum|up to|upto|"
    r"around|about|approximately|approx|\d)|$)",
    re.IGNORECASE,
)
_COUNTY_SUFFIX = re.compile(r"\s+county$", re.IGNORECASE)


def parse_query(query: str) -> ParsedConstraints:
    lowered = query.strip().lower()
    max_price = _first_number(
        lowered,
        r"(?:under|below|less than|max(?:imum)?|upto|up to|<=)\s*"
        r"(?:kshs?|kes|bob|shillings?)?\s*(\d+(?:\.\d+)?)"
        r"|(\d+(?:\.\d+)?)\s*(?:bob|kshs?|kes|shillings?)?\s*(?:and below|max)",
    )
    target_price = _first_number(
        lowered,
        r"(?:around|about|approx(?:imately)?|~)\s*"
        r"(?:kshs?|kes|bob|shillings?)?\s*(\d+(?:\.\d+)?)",
    )
    if max_price is None and target_price is None:
        max_price = _first_number(
            lowered, r"(\d+(?:\.\d+)?)\s*(?:bob|kshs?|kes|shillings?)"
        )

    location = None
    location_match = _LOCATION_CLAUSE.search(lowered)
    if location_match:
        location = re.sub(r"\b(please|now|asap|today)\b", "", location_match.group(1)).strip()
        location = _COUNTY_SUFFIX.sub("", location).strip()

    county_text = lowered.replace("-", " ")
    county = next(
        (name for name in KENYAN_COUNTIES if re.search(rf"\b{re.escape(name)}\b", county_text)),
        None,
    )
    if county and location:
        location = re.sub(rf"\b{re.escape(county)}\b", " ", location)
        location = normalize_name(location) or None

    product = _INTENT.sub(" ", lowered)
    product = _PRICE_CLAUSE.sub(" ", product)
    product = _LOCATION_CLAUSE.sub(" ", product)
    if county:
        product = re.sub(rf"\b{re.escape(county)}\b", " ", product)
        product = re.sub(r"\bcounty\b", " ", product)
    product = re.sub(r"\b(?:near|in|around|at)\b", " ", product)
    product = normalize_name(product) or normalize_name(query)

    extras = ["urgent"] if re.search(r"\b(now|asap|right now)\b", lowered) else []
    return ParsedConstraints(
        product=product,
        max_price_kes=max_price,
        target_price_kes=target_price,
        location=location or None,
        county=canonical_county(county) if county else None,
        extras=extras,
        parser="offline",
    )


def _first_number(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    return float(next(group for group in match.groups() if group))
