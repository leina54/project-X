# Software X

Software X is a FastAPI backend for finding products in local shops. Buyers can search in natural language; results include matching in-stock products, KES prices, and shop locations.

## External service

Supabase is the only external service. Search parsing and location/county matching run locally. Shop coordinates can be entered manually; distance ranking is used only when both the buyer and shop have coordinates. The app does not call Google Maps or an LLM provider.

## Set up locally

1. Create a Python environment and install the app:

   ```bash
   python3.13 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env.local
   ```

2. Set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in `.env.local` (or `.env`). The publishable key is intended for client applications; database access is restricted by per-user Row Level Security policies. Never use a Supabase secret/service-role key in the browser or commit environment files.

3. In the Supabase SQL editor, run these scripts in order:

   ```text
   sql/001_init.sql
   sql/002_validate_production_data.sql
   sql/003_supabase_auth_rls.sql
   ```

   For an existing database, inspect and fix missing shop locations/counties, unsupported county names, product descriptions over 20 words, and duplicate shops per owner using the diagnostic queries in the second script before applying it. Script 003 migrates authentication to Supabase Auth. Legacy app passwords cannot be reused; if there are existing shops, create/confirm matching Auth users (same email) in Supabase first so their shops can be linked. The migration stops if any shop owner cannot be linked; it does not delete records automatically.

   If you already ran scripts 001 and 002, run only `sql/003_supabase_auth_rls.sql` now. Its `/ready` RPC becomes available after a successful migration.

   If `/ready` returns `503` because the readiness RPC is missing (`PGRST202`), apply `sql/003_supabase_auth_rls.sql` after confirming scripts 001 and 002 completed. The app uses a publishable key and cannot apply migrations itself. If a migration reports data-validation or account-linking errors, resolve the reported issue first and rerun it; do not disable RLS or delete existing records to force readiness.

4. Start the app:

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Open [http://localhost:8000](http://localhost:8000) or [http://localhost:8000/docs](http://localhost:8000/docs) to access the API documentation and send requests. The root redirects to `/docs`; there is no separate shop-management UI. `/health` is a liveness check, and `/ready` checks Supabase connectivity.

## Using the API

Use `/docs` to register or sign in, then authorize requests using the returned Supabase access token:

1. Register with `POST /auth/register` using an email, password, and role (`shop` or `buyer`). If email confirmation is enabled, confirm the email and sign in with `POST /auth/login`.
2. In `/docs`, select **Authorize** and enter `Bearer <access_token>`.
3. Create a shop with `POST /shops`, then add products with `POST /inventory`.
4. Search available products with `POST /matching/search`.

## API reference

Create a shop with `POST /shops`:

```json
{"name":"Kileleshwa Market","location":"Kasuku Road, Kileleshwa","county":"Nairobi"}
```

Add inventory with `POST /inventory`. Product descriptions are limited to 20 words. `price_kes` is stored as a decimal with two places:

```json
{"name":"Handmade moringa soap with shea butter","price_kes":250.00,"quantity":12}
```

Search using `POST /matching/search`, for example `{"query":"moringa soap under 300 bob","county":"Nairobi"}`. Search can also take a `location` or both `user_lat` and `user_lng`. County filters use Kenya's 47 counties. Inventory listing supports `limit` and `offset`; `DELETE /inventory/{item_id}` archives an item and removes it from search results. Price values are returned as decimal strings (for example, `"250.00"`) so clients retain the two-decimal currency format. Account deletion requires a private Supabase Auth admin key, so `DELETE /auth/me` is intentionally unavailable when using only a publishable key.

## Deployment to Render

The [Render Blueprint](./render.yaml) creates a web service using `/ready` as its deployment health check.

1. Push the repository to GitHub. Do not commit `.env`; it is excluded by `.gitignore`.
2. In Render, choose **New → Blueprint**, connect the repository, and select `render.yaml`.
3. Enter `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` as Render environment variables. If a browser-based frontend is deployed on a different origin, set `CORS_ORIGINS` to a comma-separated allowlist of its exact origins.
4. Deploy and test `/health`, `/ready`, `/docs`, account registration/login, shop setup, inventory updates, and search.

Production startup requires Supabase credentials. Supabase signs and validates access tokens. The API rejects request bodies larger than 64 KiB by default. Login, registration, token, and search requests also have in-process rate limits; these limits are per application worker and reset on restart, so use a trusted edge/WAF rate limit for high-traffic public deployments. CORS is disabled for browser origins unless an explicit allowlist is configured.

## Operations and known limitations

- Keep the Supabase service-role key private and enable Supabase backups/PITR appropriate to your plan. Regularly verify that a backup can be restored; backup retention and recovery are configured in Supabase, not by this app.
- Account deletion needs a Supabase Auth admin credential; it is not exposed by the publishable-key-only deployment.
- Application logs include request method/path/status/timing and sanitized database error codes, not request bodies, passwords, or bearer tokens.
- Custom email/password accounts do not yet support email verification or password reset. Before accepting public users, move authentication to Supabase Auth or implement and configure a verified email/reset workflow.
- Location text and county are filters. Distance estimates require manually supplied shop and buyer coordinates; there is no geocoding service.
- M-Pesa, WhatsApp, image inventory, MCP, and the mobile app are outside this MVP.

## Development checks

Install test dependencies and run the test suite:

```bash
pip install -r requirements-dev.txt
pytest -q
```

GitHub Actions runs the same tests on pushes and pull requests.
