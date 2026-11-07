import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from pydantic import ValidationError
from supabase_auth.errors import AuthApiError

from app.api.deps import get_current_user
from app.core.config import Settings
from app.core.middleware import RequestGuardMiddleware
from app.main import app, settings
from app.models.user import User
from app.schemas.inventory import InventoryCreate, InventoryUpdate
from app.schemas.matching import SearchRequest
from app.schemas.shop import ShopCreate
from app.services import auth_service, inventory_service, matching_engine, query_parser


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "environment", "test")
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _user(role: str = "shop") -> User:
    return User(
        id="user-1",
        email="shop@example.com",
        role=role,
    )


def test_root_redirects_to_api_docs(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


class FakeSupabase:
    def __init__(self):
        self.rows = {}
        self.auth = FakeAuth(self)
        self.postgrest = FakePostgrest()

    def table(self, name):
        assert name == "profiles"
        return FakeProfilesQuery(self)


class FakeAuth:
    def __init__(self, supabase):
        self.supabase = supabase

    def sign_up(self, credentials):
        email = credentials["email"]
        if email in self.supabase.rows:
            raise AuthApiError("Email already registered", 422, "email_exists")
        user = SimpleNamespace(
            id=f"user-{len(self.supabase.rows) + 1}",
            email=email,
            user_metadata=credentials["options"]["data"],
            created_at=datetime.now(timezone.utc),
        )
        self.supabase.rows[email] = {
            "id": user.id,
            "email": email,
            "role": credentials["options"]["data"]["role"],
            "created_at": user.created_at.isoformat(),
        }
        return SimpleNamespace(user=user, session=self._session(user.id))

    def sign_in_with_password(self, credentials):
        email = credentials["email"]
        if email not in self.supabase.rows or credentials["password"] != "secure-pass-1":
            raise AuthApiError("Invalid credentials", 400, "invalid_credentials")
        return SimpleNamespace(
            user=SimpleNamespace(id=self.supabase.rows[email]["id"]),
            session=self._session(self.supabase.rows[email]["id"]),
        )

    def refresh_session(self, refresh_token):
        user_id = refresh_token.removeprefix("refresh-")
        row = next(row for row in self.supabase.rows.values() if row["id"] == user_id)
        return SimpleNamespace(user=SimpleNamespace(id=row["id"]), session=self._session(user_id))

    def get_user(self, token):
        user_id = token.removeprefix("access-")
        row = next(row for row in self.supabase.rows.values() if row["id"] == user_id)
        return SimpleNamespace(user=SimpleNamespace(id=user_id, email=row["email"]))

    @staticmethod
    def _session(user_id):
        return SimpleNamespace(
            access_token=f"access-{user_id}",
            refresh_token=f"refresh-{user_id}",
        )


class FakePostgrest:
    def auth(self, token):
        self.token = token


class FakeProfilesQuery:
    def __init__(self, client):
        self.client = client
        self.filters = {}

    def select(self, *_):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def limit(self, _):
        return self

    def execute(self):
        rows = [
            row
            for row in self.client.rows.values()
            if all(row.get(key) == value for key, value in self.filters.items())
        ]
        return type("Result", (), {"data": rows})()


class FakeInventoryDatabase:
    def __init__(self):
        self.shop = {"id": "shop-1", "owner_id": "user-1"}
        self.item = {
            "id": "item-1",
            "shop_id": "shop-1",
            "is_active": True,
            "quantity": 4,
        }

    def table(self, name):
        return FakeInventoryQuery(self, name)


class FakeInventoryQuery:
    def __init__(self, database, table):
        self.database = database
        self.table_name = table
        self.filters = {}
        self.action = "select"
        self.changes = {}

    def select(self, *_):
        self.action = "select"
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def limit(self, _):
        return self

    def update(self, changes):
        self.action = "update"
        self.changes = changes
        return self

    def execute(self):
        if self.table_name == "shops":
            rows = (
                [self.database.shop]
                if self.filters.get("owner_id") == self.database.shop["owner_id"]
                else []
            )
        else:
            row_matches = all(
                self.database.item.get(key) == value
                for key, value in self.filters.items()
            )
            if self.action == "update" and row_matches:
                self.database.item.update(self.changes)
            rows = [self.database.item] if row_matches else []
        return type("Result", (), {"data": rows})()


def test_register_login_and_duplicate_email(client, monkeypatch):
    fake_db = FakeSupabase()
    monkeypatch.setattr(auth_service, "get_supabase", lambda: fake_db)

    registered = client.post(
        "/auth/register",
        json={"email": " SHOP@example.com ", "password": "secure-pass-1", "role": "shop"},
    )
    assert registered.status_code == 200
    assert registered.json()["user"]["email"] == "shop@example.com"
    assert registered.json()["access_token"] == "access-user-1"
    assert fake_db.rows["shop@example.com"]["role"] == "shop"

    login = client.post(
        "/auth/login",
        json={"email": "shop@example.com", "password": "secure-pass-1"},
    )
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert login.json()["refresh_token"] == "refresh-user-1"

    duplicate = client.post(
        "/auth/register",
        json={"email": "shop@example.com", "password": "secure-pass-1", "role": "shop"},
    )
    assert duplicate.status_code == 409


def test_signup_without_email_confirmation_returns_no_session(client, monkeypatch):
    class ConfirmationAuth(FakeAuth):
        def sign_up(self, credentials):
            response = super().sign_up(credentials)
            response.session = None
            return response

    fake_db = FakeSupabase()
    fake_db.auth = ConfirmationAuth(fake_db)
    monkeypatch.setattr(auth_service, "get_supabase", lambda: fake_db)
    response = client.post(
        "/auth/register",
        json={"email": "buyer@example.com", "password": "secure-pass-1", "role": "buyer"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"] is None
    assert response.json()["requires_email_confirmation"] is True
    assert response.json()["user"]["role"] == "buyer"


def test_supabase_access_token_resolves_private_profile(client, monkeypatch):
    fake_db = FakeSupabase()
    fake_db.rows["shop@example.com"] = {
        "id": "user-1",
        "email": "shop@example.com",
        "role": "shop",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    import app.api.deps as deps_module

    monkeypatch.setattr(deps_module, "get_supabase", lambda: fake_db)
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer access-user-1"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == "user-1"
    assert response.json()["role"] == "shop"


def test_inventory_validation_limits_description_and_price():
    item = InventoryCreate(name=" Handmade soap ", price_kes="250.00", quantity=2)
    assert item.name == "Handmade soap"
    assert item.price_kes == Decimal("250.00")

    with pytest.raises(ValidationError):
        InventoryCreate(name=" ".join(["word"] * 21), price_kes="1.00", quantity=1)
    with pytest.raises(ValidationError):
        InventoryCreate(name="Soap", price_kes="1.001", quantity=1)
    with pytest.raises(ValidationError):
        InventoryUpdate()
    assert '"price_kes":"250.00"' in InventoryCreate(
        name="Soap",
        price_kes="250.00",
        quantity=1,
    ).model_dump_json()


def test_shop_schema_requires_valid_kenyan_county():
    shop = ShopCreate(name=" Shop ", location=" Main Street ", county="taita taveta")
    assert shop.county == "Taita-Taveta"
    with pytest.raises(ValidationError):
        ShopCreate(name="Shop", location="Main Street", county="Unknown")


def test_search_parser_extracts_product_price_location_and_county():
    constraints = query_parser.parse_query(
        "I need moringa soaps under 300 bob near Kileleshwa in Nairobi County"
    )
    assert constraints.product == "moringa soaps"
    assert constraints.max_price_kes == 300
    assert constraints.location == "kileleshwa"
    assert constraints.county == "Nairobi"


def test_matching_filters_location_county_and_exact_price(monkeypatch):
    fresh = datetime.now(timezone.utc).isoformat()
    candidates = [
        {
            "item": {
                "id": "item-1",
                "name": "Moringa soap",
                "normalized_name": "moringa soap",
                "price_kes": "250.00",
                "quantity": 3,
                "is_active": True,
                "last_updated_at": fresh,
            },
            "shop": {
                "id": "shop-1",
                "name": "Kileleshwa Market",
                "location": "Kasuku Road, Kileleshwa",
                "county": "Nairobi",
            },
        },
        {
            "item": {
                "id": "item-2",
                "name": "Moringa soap",
                "normalized_name": "moringa soap",
                "price_kes": "301.00",
                "quantity": 1,
                "is_active": True,
                "last_updated_at": fresh,
            },
            "shop": {
                "id": "shop-2",
                "name": "Mombasa Market",
                "location": "Old Town",
                "county": "Mombasa",
            },
        },
    ]
    monkeypatch.setattr(inventory_service, "iter_live_inventory", lambda **_: iter(candidates))
    result = matching_engine.search(
        SearchRequest(
            query="I need moringa soap under 300 bob near Kileleshwa",
            county="Nairobi",
        )
    )
    assert [match.item_id for match in result.matches] == ["item-1"]
    assert result.matches[0].price_kes == Decimal("250.00")


def test_archived_inventory_is_scoped_to_its_shop(monkeypatch):
    database = FakeInventoryDatabase()
    monkeypatch.setattr(inventory_service, "get_supabase", lambda: database)

    inventory_service.archive_item(_user("shop"), "item-1")
    assert database.item["is_active"] is False
    assert database.item["quantity"] == 0

    database.item["is_active"] = True
    database.item["quantity"] = 4
    with pytest.raises(HTTPException) as error:
        inventory_service.archive_item(_user("buyer").model_copy(update={"id": "user-2"}), "item-1")
    assert error.value.status_code == 404
    assert database.item["is_active"] is True


def test_non_shop_user_cannot_manage_inventory(client):
    app.dependency_overrides[get_current_user] = lambda: _user("buyer")
    response = client.get("/inventory")
    assert response.status_code == 403


def test_shop_inventory_list_uses_pagination(client, monkeypatch):
    seen = {}

    def list_inventory(user, *, limit, offset):
        seen.update(user_id=user.id, limit=limit, offset=offset)
        return []

    app.dependency_overrides[get_current_user] = lambda: _user("shop")
    monkeypatch.setattr(inventory_service, "list_inventory", list_inventory)
    response = client.get("/inventory?limit=15&offset=30")
    assert response.status_code == 200
    assert seen == {"user_id": "user-1", "limit": 15, "offset": 30}


def test_account_deletion_requires_admin_key(client, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: _user("buyer")
    response = client.delete("/auth/me")
    assert response.status_code == 501
    assert "admin key" in response.json()["detail"]


def test_body_limit_returns_413(client):
    response = client.post(
        "/matching/search",
        content=b"x" * (settings.max_request_body_bytes + 1),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


def test_readiness_reports_missing_database(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(
        main_module,
        "get_supabase",
        lambda: (_ for _ in ()).throw(HTTPException(status_code=503)),
    )
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "dependency": "supabase_or_schema"}


def test_readiness_requires_auth_migration(client, monkeypatch):
    class ReadinessClient:
        def rpc(self, _):
            return self

        def execute(self):
            return SimpleNamespace(data=False)

    import app.main as main_module

    monkeypatch.setattr(main_module, "get_supabase", lambda: ReadinessClient())
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["dependency"] == "supabase_schema"
    assert "sql/003_supabase_auth_rls.sql" in response.json()["next_step"]


def test_readiness_identifies_missing_rpc_migration(client, monkeypatch):
    class ReadinessClient:
        def rpc(self, _):
            raise APIError(
                {
                    "code": "PGRST202",
                    "message": "Function not found",
                }
            )

    import app.main as main_module

    monkeypatch.setattr(main_module, "get_supabase", lambda: ReadinessClient())
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependency": "supabase_schema",
        "next_step": (
            "Apply sql/003_supabase_auth_rls.sql in the Supabase SQL Editor "
            "after sql/001_init.sql and sql/002_validate_production_data.sql."
        ),
    }


def test_database_conflict_is_returned_without_internal_details(client, monkeypatch):
    def fail(**_):
        raise APIError({"code": "23505", "message": "database-specific details"})

    monkeypatch.setattr(inventory_service, "iter_live_inventory", fail)
    response = client.post("/matching/search", json={"query": "moringa soap"})
    assert response.status_code == 409
    assert "database-specific details" not in response.text


def test_rate_limiter_rejects_excess_login_requests():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    guard = RequestGuardMiddleware(
        app,
        max_body_bytes=32,
        window_seconds=60,
        auth_limit=1,
        search_limit=5,
    )

    async def make_request():
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        await guard(
            {
                "type": "http",
                "path": "/auth/login",
                "headers": [],
                "client": ("192.0.2.1", 1234),
            },
            receive,
            send,
        )
        return sent[0]["status"]

    assert asyncio.run(make_request()) == 200
    assert asyncio.run(make_request()) == 429


def test_production_settings_require_supabase_and_exact_cors_origins():
    missing = Settings(_env_file=None, environment="production")
    with pytest.raises(ValueError, match="SUPABASE_URL"):
        missing.validate_runtime()

    valid = Settings(
        _env_file=None,
        environment="production",
        supabase_url="https://example.supabase.co",
        supabase_key="test-key",
    )
    valid.validate_runtime()

    wildcard_cors = Settings(
        _env_file=None,
        environment="production",
        supabase_url="https://example.supabase.co",
        supabase_key="test-key",
        cors_origins="*",
    )
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        wildcard_cors.validate_runtime()
