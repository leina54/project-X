# Software X

Software X is a FastAPI backend for finding products in local shops. Buyers submit a natural-language search, and the API ranks in-stock items by product relevance, price, distance, and inventory freshness.

## External service

Supabase is the only external service required. The API uses it to store users, shops, and inventory. Search parsing works offline, and Nairobi seed coordinates are included for distance matching; Google Maps and LLM API keys are not needed.

## Setup

1. Create a Python virtual environment and install dependencies:

   ```bash
   python3.12 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Configure Supabase:

   ```bash
   cp .env.example .env
   ```

   Set `SUPABASE_URL` and `SUPABASE_KEY` in `.env`. Use the Supabase service-role key for the backend; keep it private and do not expose it in client-side code.

3. Run the database schema in the Supabase SQL editor:

   ```text
   sql/001_init.sql
   ```

   When upgrading an existing database, old shop locations are copied from the former neighborhood/address fields where possible. Fill in a county for each existing shop before updating that shop.

4. Start the API:

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Interactive API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

## Deploy to Render

The included [render.yaml](./render.yaml) configures a free Render web service. To publish it:

1. Push this project to a GitHub repository. Do not add or commit `.env`; it contains local secrets and is excluded by `.gitignore`.
2. In Render, choose **New → Blueprint**, connect the repository, and select `render.yaml`.
3. When prompted, set `SUPABASE_URL` and `SUPABASE_KEY` to your Supabase project URL and service-role key. Keep the key private. Render generates `SECRET_KEY` for the deployed service.
4. Deploy the Blueprint. When the service is live, open its `/docs` URL to test the API; `/health` reports service health.

The free service may spin down while idle, so the first request after a pause can take longer. The app cannot connect to Supabase until the schema in `sql/001_init.sql` has been run on your Supabase project.

## Basic workflow

1. Register a shop account with `POST /auth/register`, using `"role": "shop"`.
2. Create the shop with `POST /shops`, including its name, written location, and county:

   ```json
   {
     "name": "Kileleshwa Market",
     "location": "Kasuku Road, Kileleshwa",
     "county": "Nairobi"
   }
   ```

3. Add stock with `POST /inventory`. The product name can describe the product in up to 20 words, and `price_kes` supports up to two decimal places:

   ```json
   {
     "name": "Handmade moringa soap with shea butter",
     "price_kes": 250.00,
     "quantity": 12
   }
   ```

4. Search the live inventory with `POST /matching/search`:

   ```json
   {
     "query": "I need moringa soap under 300 bob near Kileleshwa"
   }
   ```

Buyers can register with `"role": "buyer"`. Shop creation and inventory management require a shop account and a bearer token.

## Current scope

The matching parser runs offline and recognizes common Kenyan-English price and location phrases. Built-in Nairobi coordinates support local distance estimates. Photo inventory, WhatsApp, M-Pesa, MCP, and the mobile app are not included in this MVP.
