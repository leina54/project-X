-- Add buyer search history and product-directed inquiries.
-- Run sql/001_init.sql, sql/002_validate_production_data.sql, and
-- sql/003_supabase_auth_rls.sql before this migration.

begin;

create table if not exists public.saved_searches (
  id uuid primary key default gen_random_uuid(),
  buyer_id uuid not null references public.profiles (id) on delete cascade,
  query text not null check (char_length(btrim(query)) between 2 and 500),
  parsed_constraints jsonb not null
    check (jsonb_typeof(parsed_constraints) = 'object'),
  created_at timestamptz not null default now()
);

create table if not exists public.product_inquiries (
  id uuid primary key default gen_random_uuid(),
  buyer_id uuid not null references public.profiles (id) on delete cascade,
  shop_id uuid not null references public.shops (id) on delete cascade,
  item_id uuid not null references public.inventory_items (id) on delete cascade,
  message text not null check (char_length(btrim(message)) between 1 and 1000),
  shop_reply text check (
    shop_reply is null or char_length(btrim(shop_reply)) between 1 and 2000
  ),
  status text not null default 'new'
    check (status in ('new', 'responded', 'closed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists saved_searches_buyer_created_idx
  on public.saved_searches (buyer_id, created_at desc);
create index if not exists product_inquiries_buyer_created_idx
  on public.product_inquiries (buyer_id, created_at desc);
create index if not exists product_inquiries_shop_status_created_idx
  on public.product_inquiries (shop_id, status, created_at desc);
create index if not exists product_inquiries_item_idx
  on public.product_inquiries (item_id);

alter table public.saved_searches enable row level security;
alter table public.product_inquiries enable row level security;

revoke all on public.saved_searches from anon, authenticated;
revoke all on public.product_inquiries from anon, authenticated;
grant select, insert, delete on public.saved_searches to authenticated;
grant select, insert on public.product_inquiries to authenticated;
grant update (status, shop_reply, updated_at)
  on public.product_inquiries to authenticated;

drop policy if exists saved_searches_buyer_read on public.saved_searches;
drop policy if exists saved_searches_buyer_insert on public.saved_searches;
drop policy if exists saved_searches_buyer_delete on public.saved_searches;
create policy saved_searches_buyer_read
on public.saved_searches for select to authenticated
using (
  buyer_id = (select auth.uid())
  and exists (
    select 1 from public.profiles
    where profiles.id = (select auth.uid())
      and profiles.role = 'buyer'
  )
);
create policy saved_searches_buyer_insert
on public.saved_searches for insert to authenticated
with check (
  buyer_id = (select auth.uid())
  and exists (
    select 1 from public.profiles
    where profiles.id = (select auth.uid())
      and profiles.role = 'buyer'
  )
);
create policy saved_searches_buyer_delete
on public.saved_searches for delete to authenticated
using (
  buyer_id = (select auth.uid())
  and exists (
    select 1 from public.profiles
    where profiles.id = (select auth.uid())
      and profiles.role = 'buyer'
  )
);

drop policy if exists product_inquiries_buyer_read on public.product_inquiries;
drop policy if exists product_inquiries_shop_read on public.product_inquiries;
drop policy if exists product_inquiries_buyer_insert on public.product_inquiries;
drop policy if exists product_inquiries_shop_update on public.product_inquiries;
create policy product_inquiries_buyer_read
on public.product_inquiries for select to authenticated
using (
  buyer_id = (select auth.uid())
  and exists (
    select 1 from public.profiles
    where profiles.id = (select auth.uid())
      and profiles.role = 'buyer'
  )
);
create policy product_inquiries_shop_read
on public.product_inquiries for select to authenticated
using (
  exists (
    select 1 from public.shops
    where shops.id = product_inquiries.shop_id
      and shops.owner_id = (select auth.uid())
  )
);
create policy product_inquiries_buyer_insert
on public.product_inquiries for insert to authenticated
with check (
  buyer_id = (select auth.uid())
  and exists (
    select 1 from public.profiles
    where profiles.id = (select auth.uid())
      and profiles.role = 'buyer'
  )
  and exists (
    select 1 from public.inventory_items
    where inventory_items.id = product_inquiries.item_id
      and inventory_items.shop_id = product_inquiries.shop_id
      and inventory_items.is_active
      and inventory_items.quantity > 0
  )
);
create policy product_inquiries_shop_update
on public.product_inquiries for update to authenticated
using (
  exists (
    select 1 from public.shops
    where shops.id = product_inquiries.shop_id
      and shops.owner_id = (select auth.uid())
  )
)
with check (
  exists (
    select 1 from public.shops
    where shops.id = product_inquiries.shop_id
      and shops.owner_id = (select auth.uid())
  )
);

create or replace function public.backend_readiness()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select to_regclass('public.profiles') is not null
     and to_regclass('public.shops') is not null
     and to_regclass('public.inventory_items') is not null
     and to_regclass('public.saved_searches') is not null
     and to_regclass('public.product_inquiries') is not null
     and coalesce((
       select relrowsecurity
       from pg_class
       where oid = to_regclass('public.profiles')
     ), false)
     and coalesce((
       select relrowsecurity
       from pg_class
       where oid = to_regclass('public.shops')
     ), false)
     and coalesce((
       select relrowsecurity
       from pg_class
       where oid = to_regclass('public.inventory_items')
     ), false)
     and coalesce((
       select relrowsecurity
       from pg_class
       where oid = to_regclass('public.saved_searches')
     ), false)
     and coalesce((
       select relrowsecurity
       from pg_class
       where oid = to_regclass('public.product_inquiries')
     ), false)
     and has_table_privilege('anon', 'public.shops', 'select')
     and has_table_privilege('anon', 'public.inventory_items', 'select');
$$;
grant execute on function public.backend_readiness() to anon, authenticated;

create or replace function public.backend_inquiries_readiness()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select public.backend_readiness()
     and to_regclass('public.saved_searches') is not null
     and to_regclass('public.product_inquiries') is not null
     and coalesce((
       select relrowsecurity
       from pg_class
       where oid = to_regclass('public.saved_searches')
     ), false)
     and coalesce((
       select relrowsecurity
       from pg_class
       where oid = to_regclass('public.product_inquiries')
     ), false);
$$;
grant execute on function public.backend_inquiries_readiness() to anon, authenticated;

notify pgrst, 'reload schema';

commit;
