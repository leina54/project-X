-- Software X MVP schema
-- Run this in the Supabase SQL editor before using the API.

create extension if not exists pgcrypto;

create table if not exists public.users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  hashed_password text not null,
  role text not null check (role in ('buyer', 'shop')),
  created_at timestamptz not null default now()
);

create table if not exists public.shops (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.users (id) on delete cascade,
  name text not null,
  location text not null,
  county text not null,
  address text,
  neighborhood text,
  lat double precision,
  lng double precision,
  created_at timestamptz not null default now()
);

create table if not exists public.inventory_items (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references public.shops (id) on delete cascade,
  name text not null,
  normalized_name text not null,
  price_kes numeric(12, 2) not null check (price_kes >= 0),
  quantity integer not null default 0 check (quantity >= 0),
  is_active boolean not null default true,
  last_updated_at timestamptz not null default now()
);

-- Keep existing installations usable while requiring new and updated rows to
-- satisfy the current data rules. Existing shop locations are backfilled where
-- possible; missing locations/counties and overlong product names need manual
-- cleanup before those legacy rows can be updated if present.
alter table public.shops add column if not exists location text;
alter table public.shops add column if not exists county text;
alter table public.inventory_items add column if not exists is_active boolean not null default true;

update public.shops
set location = coalesce(nullif(btrim(neighborhood), ''), nullif(btrim(address), ''))
where (location is null or btrim(location) = '')
  and coalesce(nullif(btrim(neighborhood), ''), nullif(btrim(address), '')) is not null;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'shops_location_required'
      and conrelid = 'public.shops'::regclass
  ) then
    alter table public.shops
      add constraint shops_location_required
      check (location is not null and location ~ '[^[:space:]]') not valid;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'shops_county_required'
      and conrelid = 'public.shops'::regclass
  ) then
    alter table public.shops
      add constraint shops_county_required
      check (county is not null and county ~ '[^[:space:]]') not valid;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'shops_county_known'
      and conrelid = 'public.shops'::regclass
  ) then
    alter table public.shops
      add constraint shops_county_known
      check (
        lower(replace(btrim(county), '-', ' ')) in (
          'baringo', 'bomet', 'bungoma', 'busia', 'elgeyo marakwet',
          'embu', 'garissa', 'homa bay', 'isiolo', 'kajiado', 'kakamega',
          'kericho', 'kiambu', 'kilifi', 'kirinyaga', 'kisii', 'kisumu',
          'kitui', 'kwale', 'laikipia', 'lamu', 'machakos', 'makueni',
          'mandera', 'marsabit', 'meru', 'migori', 'mombasa', 'murang''a',
          'nakuru', 'nandi', 'narok', 'nyamira', 'nyandarua', 'nyeri',
          'samburu', 'siaya', 'taita taveta', 'tana river', 'tharaka nithi',
          'trans nzoia', 'turkana', 'uasin gishu', 'vihiga', 'wajir',
          'west pokot', 'nairobi'
        )
      ) not valid;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'inventory_name_max_20_words'
      and conrelid = 'public.inventory_items'::regclass
  ) then
    alter table public.inventory_items
      add constraint inventory_name_max_20_words
      check (
        name ~ '[^[:space:]]'
        and cardinality(regexp_split_to_array(btrim(name), E'\\s+')) <= 20
      ) not valid;
  end if;
end
$$;

create index if not exists shops_owner_id_idx on public.shops (owner_id);
create index if not exists shops_county_idx on public.shops (county);
create index if not exists shops_neighborhood_idx on public.shops (neighborhood);
create index if not exists shops_location_idx on public.shops (lat, lng);
create index if not exists inventory_shop_id_idx on public.inventory_items (shop_id);
create index if not exists inventory_normalized_name_idx on public.inventory_items (normalized_name);
create index if not exists inventory_price_idx on public.inventory_items (price_kes);
create index if not exists inventory_last_updated_idx on public.inventory_items (last_updated_at desc);
create index if not exists inventory_in_stock_idx on public.inventory_items (quantity) where quantity > 0;
create index if not exists inventory_active_idx on public.inventory_items (shop_id, last_updated_at desc) where is_active;

alter table public.users enable row level security;
alter table public.shops enable row level security;
alter table public.inventory_items enable row level security;

-- Backend uses the service role key, which bypasses RLS.
-- These policies keep the tables locked down for the anon key.
drop policy if exists users_service_only on public.users;
create policy users_service_only on public.users for all using (false) with check (false);

drop policy if exists shops_service_only on public.shops;
create policy shops_service_only on public.shops for all using (false) with check (false);

drop policy if exists inventory_service_only on public.inventory_items;
create policy inventory_service_only on public.inventory_items for all using (false) with check (false);
