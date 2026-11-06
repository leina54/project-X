from decimal import Decimal

from app.schemas.matching import (
    MatchResult,
    ParsedConstraints,
    ScoreBreakdown,
    SearchRequest,
    SearchResponse,
)
from app.services import inventory_service, llm_service, maps_service
from app.utils.helpers import parse_iso_datetime, tokenize, utcnow

WEIGHTS = {
    "relevance": 0.40,
    "price_fit": 0.25,
    "distance": 0.20,
    "freshness": 0.15,
}


def search(payload: SearchRequest) -> SearchResponse:
    constraints = llm_service.parse_query(payload.query)
    origin = _origin(payload, constraints)
    candidates = inventory_service.list_live_inventory()

    matches: list[MatchResult] = []
    product_tokens = tokenize(constraints.product)
    for row in candidates:
        shop = inventory_service.maybe_geocode_shop(row["shop"])
        item = row["item"]
        if not _passes_filters(item, constraints, product_tokens):
            continue
        distance = maps_service.distance_km(origin, shop.get("lat"), shop.get("lng"))
        breakdown = _score(item, constraints, product_tokens, distance)
        matches.append(
            MatchResult(
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
        )

    matches.sort(key=lambda match: match.score.total, reverse=True)
    return SearchResponse(
        query=payload.query,
        constraints=constraints,
        matches=matches[: payload.limit],
    )


def _origin(payload: SearchRequest, constraints: ParsedConstraints) -> tuple[float, float] | None:
    if payload.user_lat is not None and payload.user_lng is not None:
        return payload.user_lat, payload.user_lng
    if constraints.location:
        return maps_service.geocode(constraints.location)
    return None


def _passes_filters(item: dict, constraints: ParsedConstraints, product_tokens: set[str]) -> bool:
    name_tokens = tokenize(item.get("normalized_name") or item.get("name") or "")
    if product_tokens and name_tokens.isdisjoint(product_tokens):
        # Keep items that contain the full product string as a substring.
        haystack = item.get("normalized_name") or ""
        if constraints.product not in haystack:
            return False
    if constraints.max_price_kes is not None and float(item["price_kes"]) > constraints.max_price_kes * 1.25:
        return False
    return True


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
    name_tokens = tokenize(item.get("normalized_name") or item.get("name") or "")
    if not product_tokens or not name_tokens:
        return 0.0
    overlap = len(product_tokens & name_tokens) / len(product_tokens)
    if (item.get("normalized_name") or "").startswith(" ".join(sorted(product_tokens)[:1])):
        overlap = min(1.0, overlap + 0.1)
    return overlap


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
