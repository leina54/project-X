import math
import heapq
from decimal import Decimal

from app.schemas.matching import (
    MatchResult,
    ParsedConstraints,
    ScoreBreakdown,
    SearchRequest,
    SearchResponse,
)
from app.services import inventory_service, query_parser
from app.utils.helpers import normalize_name, parse_iso_datetime, tokenize, utcnow

WEIGHTS = {
    "relevance": 0.40,
    "price_fit": 0.25,
    "distance": 0.20,
    "freshness": 0.15,
}


def search(payload: SearchRequest) -> SearchResponse:
    constraints = query_parser.parse_query(payload.query)
    if payload.location:
        constraints.location = payload.location.strip()
    if payload.county:
        constraints.county = payload.county.strip()
    origin = _origin(payload)
    candidates = inventory_service.iter_live_inventory(
        county=constraints.county,
        max_price_kes=constraints.max_price_kes,
    )
    ranked_matches: list[tuple[float, int, MatchResult]] = []
    product_tokens = _search_tokens(constraints.product)
    for candidate_index, row in enumerate(candidates):
        shop = row["shop"]
        item = row["item"]
        if not _passes_filters(item, shop, constraints, product_tokens):
            continue
        distance = _distance_km(origin, shop.get("lat"), shop.get("lng"))
        breakdown = _score(item, constraints, product_tokens, distance)
        match = MatchResult(
                shop_id=shop["id"],
                shop_name=shop["name"],
                location=shop.get("location"),
                county=shop.get("county"),
                neighborhood=shop.get("neighborhood"),
                item_id=item["id"],
                item_name=item["name"],
                price_kes=Decimal(str(item["price_kes"])).quantize(Decimal("0.01")),
                quantity=int(item["quantity"]),
                distance_km=distance,
                last_updated_at=parse_iso_datetime(item.get("last_updated_at")),
                score=breakdown,
            )
        ranked_entry = (match.score.total, -candidate_index, match)
        if len(ranked_matches) < payload.limit:
            heapq.heappush(ranked_matches, ranked_entry)
        elif ranked_entry[:2] > ranked_matches[0][:2]:
            heapq.heapreplace(ranked_matches, ranked_entry)
    ranked_matches.sort(key=lambda entry: entry[:2], reverse=True)
    return SearchResponse(
        query=payload.query,
        constraints=constraints,
        matches=[entry[2] for entry in ranked_matches],
    )


def _origin(payload: SearchRequest) -> tuple[float, float] | None:
    if payload.user_lat is not None and payload.user_lng is not None:
        return payload.user_lat, payload.user_lng
    return None


def _passes_filters(
    item: dict,
    shop: dict,
    constraints: ParsedConstraints,
    product_tokens: set[str],
) -> bool:
    name_tokens = _search_tokens(item.get("normalized_name") or item.get("name") or "")
    if product_tokens and name_tokens.isdisjoint(product_tokens):
        haystack = item.get("normalized_name") or ""
        if constraints.product not in haystack:
            return False
    if constraints.max_price_kes is not None and float(item["price_kes"]) > constraints.max_price_kes:
        return False
    if constraints.county and _normalize(shop.get("county")) != _normalize(constraints.county):
        return False
    if constraints.location:
        location_tokens = _search_tokens(constraints.location)
        shop_location_tokens = _search_tokens(
            " ".join(
                str(shop.get(field) or "")
                for field in ("location", "neighborhood", "address")
            )
        )
        if not location_tokens.issubset(shop_location_tokens):
            return False
    if not item.get("is_active", True) or int(item.get("quantity") or 0) <= 0:
        return False
    return True


def _normalize(value: object) -> str:
    return normalize_name(str(value or ""))


def _search_tokens(value: object) -> set[str]:
    tokens = tokenize(str(value or ""))
    normalized = set()
    for token in tokens:
        if len(token) > 4 and token.endswith("ies"):
            token = f"{token[:-3]}y"
        elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        normalized.add(token)
    return normalized


def _distance_km(
    origin: tuple[float, float] | None,
    dest_lat: float | None,
    dest_lng: float | None,
) -> float | None:
    if origin is None or dest_lat is None or dest_lng is None:
        return None
    radius = 6371.0
    phi1, phi2 = math.radians(origin[0]), math.radians(dest_lat)
    d_phi = math.radians(dest_lat - origin[0])
    d_lambda = math.radians(dest_lng - origin[1])
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return round(2 * radius * math.asin(math.sqrt(a)), 3)


def _score(
    item: dict,
    constraints: ParsedConstraints,
    product_tokens: set[str],
    distance_km: float | None,
) -> ScoreBreakdown:
    relevance = _relevance(item, product_tokens)
    price_fit = _price_fit(float(item["price_kes"]), constraints)
    distance = _distance_fit(distance_km)
    freshness = _freshness(item.get("last_updated_at"))
    total = (
        WEIGHTS["relevance"] * relevance
        + WEIGHTS["price_fit"] * price_fit
        + WEIGHTS["distance"] * distance
        + WEIGHTS["freshness"] * freshness
    )
    return ScoreBreakdown(
        relevance=round(relevance, 4),
        price_fit=round(price_fit, 4),
        distance=round(distance, 4),
        freshness=round(freshness, 4),
        total=round(total, 4),
    )


def _relevance(item: dict, product_tokens: set[str]) -> float:
    name_tokens = _search_tokens(item.get("normalized_name") or item.get("name") or "")
    if not product_tokens or not name_tokens:
        return 0.0
    return len(product_tokens & name_tokens) / len(product_tokens)


def _price_fit(price: float, constraints: ParsedConstraints) -> float:
    if constraints.max_price_kes is not None:
        cap = constraints.max_price_kes
        if price <= cap:
            return 1.0
        overshoot = (price - cap) / cap
        return max(0.0, 1.0 - overshoot)
    if constraints.target_price_kes is not None:
        target = constraints.target_price_kes
        if target <= 0:
            return 1.0
        return max(0.0, 1.0 - abs(price - target) / target)
    return 0.7


def _distance_fit(distance_km: float | None) -> float:
    if distance_km is None:
        return 0.5
    return max(0.0, 1.0 - (distance_km / 10.0))


def _freshness(last_updated_at: object) -> float:
    if last_updated_at is None:
        return 0.3
    updated = parse_iso_datetime(last_updated_at)  # type: ignore[arg-type]
    if updated is None:
        return 0.3
    hours = max(0.0, (utcnow() - updated).total_seconds() / 3600)
    if hours <= 24:
        return 1.0
    return max(0.0, 1.0 - ((hours - 24) / 168))
