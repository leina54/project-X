#!/usr/bin/env python3
"""Idempotently seed the explicitly authorized Software X demo Supabase project."""

from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values
from supabase import Client, create_client

from app.services.query_parser import parse_query
from app.utils.helpers import normalize_name, utcnow

SEED_TAG = "software-x-demo-2026-v1"
EMAIL_DOMAIN = "example.com"
CREDENTIALS_FILE = ROOT / ".softwarex-demo-credentials.json"

SHOPS = [
    ("Nairobi Fresh Basket", "Gikomba Market, Nairobi", "Nairobi", -1.2864, 36.8172),
    ("Westlands Green Grocers", "Sarit Centre, Westlands", "Nairobi", -1.2676, 36.8108),
    ("Mombasa Coast Market", "Mwembe Tayari, Mombasa", "Mombasa", -4.0435, 39.6682),
    ("Kisumu Lakeside Produce", "Kibuye Market, Kisumu", "Kisumu", -0.0917, 34.7680),
    ("Nakuru Valley Foods", "Nakuru Town Market", "Nakuru", -0.3031, 36.0800),
    ("Kiambu Harvest Shop", "Kiambu Town Centre", "Kiambu", -1.1714, 36.8356),
    ("Machakos Farm Store", "Machakos Town Market", "Machakos", -1.5177, 37.2634),
    ("Eldoret Grain and Greens", "Kenyatta Street, Eldoret", "Uasin Gishu", 0.5143, 35.2698),
    ("Nyeri Highland Produce", "Nyeri Town Market", "Nyeri", -0.4197, 36.9553),
    ("Meru Family Grocers", "Makutano Market, Meru", "Meru", 0.0467, 37.6559),
    ("Kakamega Fresh Corner", "Kakamega Town Market", "Kakamega", 0.2827, 34.7519),
    ("Thika Value Foods", "Thika Town Centre", "Kiambu", -1.0396, 37.0900),
    ("Kisii Farm Gate", "Kisii Main Market", "Kisii", -0.6817, 34.7667),
    ("Kitui Grain House", "Kitui Town Market", "Kitui", -1.3667, 38.0106),
    ("Embu Green Basket", "Embu Town Market", "Embu", -0.5389, 37.4596),
    ("Kericho Tea Country Store", "Kericho Town Centre", "Kericho", -0.3689, 35.2863),
    ("Kilifi Coastal Grocers", "Kilifi Town Market", "Kilifi", -3.6305, 39.8499),
    ("Bungoma Harvest Hub", "Bungoma Town Market", "Bungoma", 0.5635, 34.5606),
    ("Garissa Community Market", "Garissa Town Market", "Garissa", -0.4536, 39.6401),
    ("Narok Fresh Supplies", "Narok Town Market", "Narok", -1.0783, 35.8601),
]

PRODUCTS = [
    [
        ("Fresh red tomatoes from local farms", "120.00", 45),
        ("Ripe sweet bananas by the bunch", "180.00", 30),
        ("Farm fresh spinach leafy greens", "60.00", 35),
    ],
    [
        ("Organic avocado fruit ready to eat", "80.00", 28),
        ("Fresh mangoes sweet seasonal produce", "150.00", 32),
        ("Free range eggs tray of thirty", "520.00", 18),
    ],
    [
        ("Coconut cooking oil cold pressed", "650.00", 14),
        ("Fresh cassava roots locally harvested", "110.00", 25),
        ("Coastal red onions per kilogram", "140.00", 40),
    ],
    [
        ("Fresh tilapia fish cleaned per kilogram", "680.00", 16),
        ("Sweet potatoes freshly harvested", "100.00", 30),
        ("Green kale sukuma wiki bundle", "35.00", 55),
    ],
    [
        ("Potatoes from highland farms per kilogram", "95.00", 60),
        ("Carrots freshly washed per kilogram", "130.00", 34),
        ("Farm fresh milk one litre", "90.00", 26),
    ],
    [
        ("Fresh garden peas shelled per kilogram", "240.00", 22),
        ("Green cooking bananas matoke bunch", "220.00", 20),
        ("Organic coriander dhania fresh bunch", "30.00", 48),
    ],
    [
        ("Dry maize flour two kilogram packet", "190.00", 36),
        ("Fresh green beans per kilogram", "170.00", 25),
        ("Red kidney beans sorted per kilogram", "260.00", 29),
    ],
    [
        ("Dry white maize grain per kilogram", "75.00", 90),
        ("Fresh cabbages medium size each", "85.00", 40),
        ("Groundnuts roasted unsalted per packet", "150.00", 27),
    ],
    [
        ("Highland green peas fresh per kilogram", "210.00", 23),
        ("Fresh apples crisp red per kilogram", "320.00", 20),
        ("Brown onions medium size per kilogram", "145.00", 35),
    ],
    [
        ("Fresh passion fruit sweet purple per kilogram", "230.00", 19),
        ("Irish potatoes clean per kilogram", "100.00", 55),
        ("Fresh traditional kunde greens bundle", "50.00", 32),
    ],
    [
        ("Sweet potatoes orange flesh per kilogram", "125.00", 33),
        ("Fresh maize cobs six piece pack", "160.00", 24),
        ("Ripe pawpaw fruit medium size", "170.00", 17),
    ],
    [
        ("Fresh button mushrooms packed 250 grams", "280.00", 15),
        ("Red capsicum peppers per kilogram", "300.00", 18),
        ("Fresh broccoli heads each", "140.00", 21),
    ],
    [
        ("Fresh bananas sweet ripe per bunch", "175.00", 35),
        ("Cowpeas kunde dry beans per kilogram", "240.00", 26),
        ("Fresh tomatoes firm per kilogram", "125.00", 42),
    ],
    [
        ("Green grams mung beans per kilogram", "230.00", 31),
        ("Sorghum flour locally milled two kilogram", "260.00", 18),
        ("Fresh pumpkin slices per kilogram", "110.00", 24),
    ],
    [
        ("Fresh oranges juicy medium per kilogram", "160.00", 38),
        ("Dry maize flour locally milled two kilogram", "185.00", 34),
        ("Fresh arrowroot roots per kilogram", "140.00", 20),
    ],
    [
        ("Fresh tea leaves packed 500 grams", "240.00", 19),
        ("Farm fresh eggs tray of fifteen", "280.00", 23),
        ("Fresh garden cucumbers per kilogram", "120.00", 30),
    ],
    [
        ("Fresh coconuts mature each", "100.00", 28),
        ("Ripe pineapples sweet medium size", "190.00", 21),
        ("Fresh green okra per kilogram", "180.00", 16),
    ],
    [
        ("Dry yellow beans sorted per kilogram", "250.00", 37),
        ("Fresh local honey jar 500 grams", "700.00", 12),
        ("Fresh kale sukuma wiki large bundle", "40.00", 50),
    ],
    [
        ("Dry rice pishori per kilogram", "220.00", 41),
        ("Fresh goat milk one litre", "140.00", 18),
        ("Sweet ripe watermelons each", "350.00", 14),
    ],
    [
        ("Fresh local potatoes per kilogram", "105.00", 44),
        ("Ripe avocados creamy medium size", "75.00", 30),
        ("Fresh carrots crunchy per kilogram", "125.00", 27),
    ],
]

INQUIRY_MESSAGES = [
    "Hello, is this product available today?",
    "Can I reserve this item for collection this afternoon?",
    "Please let me know whether you have more stock.",
    "Do you offer pickup at your shop location?",
    "I am interested in buying this. Is the listed price current?",
]

SEARCH_SUFFIXES = [
    "nearby at a fair price",
    "available this week",
    "for family shopping",
    "in stock near me",
    "at a local shop",
]


def _environment() -> dict[str, str]:
    values: dict[str, str] = {}
    for filename in (".env.local", ".env"):
        path = ROOT / filename
        if path.is_file():
            values.update(
                {
                    key: value
                    for key, value in dotenv_values(path).items()
                    if key and value
                }
            )
    values.update({key: value for key, value in os.environ.items() if value})
    return values


def _credentials_path() -> Path:
    return CREDENTIALS_FILE


def _save_credentials(credentials: dict[str, dict[str, str]]) -> None:
    path = _credentials_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(credentials, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def _load_credentials() -> dict[str, dict[str, str]]:
    path = _credentials_path()
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Demo credentials file is unreadable; inspect it locally") from error
    if not isinstance(value, dict):
        raise RuntimeError("Demo credentials file has an invalid format")
    return value


def _user_email(role: str, index: int) -> str:
    kind = "shop" if role == "shop" else "buyer"
    return f"softwarex-demo-{kind}-{index:02d}@{EMAIL_DOMAIN}"


def _list_users(client: Client) -> dict[str, Any]:
    users: dict[str, Any] = {}
    page = 1
    per_page = 1000
    while True:
        page_users = client.auth.admin.list_users(page=page, per_page=per_page)
        for user in page_users:
            if user.email:
                users[user.email.lower()] = user
        if len(page_users) < per_page:
            return users
        page += 1


def _require_seed_ownership(users: dict[str, Any]) -> None:
    seeded = [
        (_user_email(role, index), role)
        for role in ("shop", "buyer")
        for index in range(1, 21)
    ]
    for email, role in seeded:
        existing = users.get(email)
        if existing is None:
            continue
        metadata = existing.user_metadata or {}
        if metadata.get("software_x_seed") != SEED_TAG or metadata.get("role") != role:
            raise RuntimeError(
                f"Refusing to overwrite an existing account at {email}; "
                "it is not marked as this script's demo account."
            )


def _ensure_users(
    client: Client,
    users: dict[str, Any],
    credentials: dict[str, dict[str, str]],
) -> dict[str, dict[str, Any]]:
    identities: dict[str, dict[str, Any]] = {"shop": {}, "buyer": {}}
    for role in ("shop", "buyer"):
        for index in range(1, 21):
            email = _user_email(role, index)
            password = credentials.get(email, {}).get("password") or secrets.token_urlsafe(32)
            attributes = {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {
                    "role": role,
                    "software_x_seed": SEED_TAG,
                    "display_name": (
                        f"Demo Shop Owner {index:02d}"
                        if role == "shop"
                        else f"Demo Buyer {index:02d}"
                    ),
                },
            }
            existing = users.get(email)
            if existing is None:
                user = client.auth.admin.create_user(attributes).user
            else:
                user = client.auth.admin.update_user_by_id(existing.id, attributes).user

            credentials[email] = {"role": role, "password": password}
            _save_credentials(credentials)
            identities[role][index] = {"id": user.id, "email": email}
            users[email] = user
    return identities


def _authenticated_clients(
    url: str,
    publishable_key: str,
    identities: dict[str, dict[str, Any]],
    credentials: dict[str, dict[str, str]],
) -> dict[str, dict[int, Client]]:
    clients: dict[str, dict[int, Client]] = {"shop": {}, "buyer": {}}
    for role, accounts in identities.items():
        for index, account in accounts.items():
            email = account["email"]
            user_client = create_client(url, publishable_key)
            session = user_client.auth.sign_in_with_password(
                {
                    "email": email,
                    "password": credentials[email]["password"],
                }
            )
            profile = (
                user_client.table("profiles")
                .select("id,role")
                .eq("id", session.user.id)
                .limit(1)
                .execute()
                .data
            )
            if not profile or profile[0]["role"] != role:
                raise RuntimeError(
                    f"Account profile is missing or has the wrong role for {email}."
                )
            clients[role][index] = user_client
    return clients


def _validate_existing_shops(
    shop_clients: dict[int, Client],
    shop_accounts: dict[int, dict[str, Any]],
) -> None:
    for index, client in shop_clients.items():
        shops = (
            client.table("shops")
            .select("id,name")
            .eq("owner_id", shop_accounts[index]["id"])
            .execute()
            .data
            or []
        )
        if any(not shop["name"].startswith("[DEMO] ") for shop in shops):
            raise RuntimeError(
                f"Refusing to change existing non-demo shop data for account {index}."
            )


def _ensure_shop(client: Client, owner_id: str, index: int) -> dict[str, Any]:
    name, location, county, lat, lng = SHOPS[index - 1]
    existing = (
        client.table("shops")
        .select("*")
        .eq("owner_id", owner_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        row = existing[0]
        if not row["name"].startswith("[DEMO] "):
            raise RuntimeError(
                f"Refusing to attach demo listings to non-demo shop {row['name']}."
            )
        return row
    created = (
        client.table("shops")
        .insert(
            {
                "owner_id": owner_id,
                "name": f"[DEMO] {name}",
                "location": location,
                "county": county,
                "neighborhood": location.split(",")[0],
                "address": location,
                "lat": lat,
                "lng": lng,
            }
        )
        .execute()
        .data
    )
    if not created:
        raise RuntimeError(f"Shop insert returned no row for demo shop {index}.")
    return created[0]


def _ensure_products(
    client: Client,
    shop_id: str,
    index: int,
) -> list[dict[str, Any]]:
    existing = (
        client.table("inventory_items")
        .select("*")
        .eq("shop_id", shop_id)
        .execute()
        .data
        or []
    )
    by_name = {row["name"]: row for row in existing}
    output = []
    for name, price, quantity in PRODUCTS[index - 1]:
        row = by_name.get(name)
        if row is None:
            created = (
                client.table("inventory_items")
                .insert(
                    {
                        "shop_id": shop_id,
                        "name": name,
                        "normalized_name": normalize_name(name),
                        "price_kes": price,
                        "quantity": quantity,
                        "is_active": True,
                        "last_updated_at": utcnow().isoformat(),
                    }
                )
                .execute()
                .data
            )
            if not created:
                raise RuntimeError(f"Product insert returned no row for demo shop {index}.")
            row = created[0]
        output.append(row)
    return output


def _ensure_saved_search(
    client: Client,
    buyer_id: str,
    query: str,
) -> None:
    existing = (
        client.table("saved_searches")
        .select("id")
        .eq("buyer_id", buyer_id)
        .eq("query", query)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        return
    constraints = parse_query(query)
    client.table("saved_searches").insert(
        {
            "buyer_id": buyer_id,
            "query": query,
            "parsed_constraints": constraints.model_dump(mode="json"),
        }
    ).execute()


def _ensure_inquiry(
    client: Client,
    buyer_id: str,
    shop_id: str,
    item_id: str,
    message: str,
    index: int,
) -> None:
    existing = (
        client.table("product_inquiries")
        .select("id")
        .eq("buyer_id", buyer_id)
        .eq("item_id", item_id)
        .eq("message", message)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        return
    status = ("new", "responded", "closed", "new", "responded")[index % 5]
    client.table("product_inquiries").insert(
        {
            "buyer_id": buyer_id,
            "shop_id": shop_id,
            "item_id": item_id,
            "message": message,
            "shop_reply": (
                "Yes, this item is available. Please contact the shop to arrange pickup."
                if status == "responded"
                else None
            ),
            "status": status,
        }
    ).execute()


def seed(client: Client, url: str, publishable_key: str) -> dict[str, int]:
    users = _list_users(client)
    _require_seed_ownership(users)
    credentials = _load_credentials()
    identities = _ensure_users(client, users, credentials)
    clients = _authenticated_clients(
        url,
        publishable_key,
        identities,
        credentials,
    )
    shop_clients = clients["shop"]
    buyer_clients = clients["buyer"]
    _validate_existing_shops(shop_clients, identities["shop"])

    seeded_shops: list[dict[str, Any]] = []
    seeded_items: list[list[dict[str, Any]]] = []
    for index in range(1, 21):
        shop = _ensure_shop(
            shop_clients[index], identities["shop"][index]["id"], index
        )
        items = _ensure_products(shop_clients[index], shop["id"], index)
        seeded_shops.append(shop)
        seeded_items.append(items)

    saved_search_count = 0
    inquiry_count = 0
    for buyer_index in range(1, 21):
        buyer = identities["buyer"][buyer_index]
        first_shop_index = buyer_index - 1
        second_shop_index = (buyer_index + 4) % 20
        for shop_index in (first_shop_index, second_shop_index):
            shop = seeded_shops[shop_index]
            item = seeded_items[shop_index][(buyer_index - 1) % 3]
            search = (
                f"{item['name']} near {shop['county']} "
                f"{SEARCH_SUFFIXES[(buyer_index + shop_index) % len(SEARCH_SUFFIXES)]}"
            )
            _ensure_saved_search(buyer_clients[buyer_index], buyer["id"], search)
            saved_search_count += 1
            message = INQUIRY_MESSAGES[(buyer_index + shop_index) % len(INQUIRY_MESSAGES)]
            _ensure_inquiry(
                buyer_clients[buyer_index],
                buyer["id"],
                shop["id"],
                item["id"],
                message,
                buyer_index + shop_index,
            )
            inquiry_count += 1

    return {
        "shop_accounts": len(identities["shop"]),
        "buyer_accounts": len(identities["buyer"]),
        "shops": len(seeded_shops),
        "products": sum(len(items) for items in seeded_items),
        "saved_searches": saved_search_count,
        "product_inquiries": inquiry_count,
    }


def main() -> int:
    env = _environment()
    if env.get("SOFTWAREX_ALLOW_DEMO_SEED") != "YES":
        print("Refusing to write. Set SOFTWAREX_ALLOW_DEMO_SEED=YES for this run.", file=sys.stderr)
        return 2

    url = env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL")
    publishable_key = (
        env.get("SUPABASE_PUBLISHABLE_KEY")
        or env.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
        or env.get("SUPABASE_KEY")
    )
    admin_key = next(
        (
            env.get(name)
            for name in (
                "SUPABASE_SECRET_KEY",
                "SUPABASE_SERVICE_ROLE_KEY",
                "SUPABASE_SERVICE_KEY",
            )
            if env.get(name)
        ),
        None,
    )
    if not url or not admin_key or not publishable_key:
        print(
            "Missing Supabase URL, private admin key, or publishable key in local environment.",
            file=sys.stderr,
        )
        return 2

    try:
        admin_client = create_client(url, admin_key)
        counts = seed(admin_client, url, publishable_key)
    except Exception as error:
        print(
            f"Seeding stopped with {type(error).__name__}. "
            "Earlier successful inserts are preserved; rerun to resume safely.",
            file=sys.stderr,
        )
        return 1

    print("Demo seed complete:")
    for label, count in counts.items():
        print(f"  {label}: {count}")
    print(f"Generated account passwords are in {CREDENTIALS_FILE} (local, git-ignored).")
    print("Demo accounts are confirmed individually; project-wide email confirmation was not changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
