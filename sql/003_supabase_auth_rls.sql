-- Migrate the API from private app-managed passwords to Supabase Auth.
-- Run sql/001_init.sql and sql/002_validate_production_data.sql first.
-- The publishable key is intentionally insufficient for bypassing RLS.

begin;

do $$
begin
  if to_regclass('public.users') is not null
     and to_regclass('public.legacy_users') is null then
    alter table public.users rename to legacy_users;
  end if;
end
$$;

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null unique,
  role text not null check (role in ('buyer', 'shop')),
  created_at timestamptz not null default now()
);

insert into public.profiles (id, email, role, created_at)
select
  auth_user.id,
  lower(auth_user.email),
  case
    when auth_user.raw_user_meta_data ->> 'role' in ('buyer', 'shop')
      then auth_user.raw_user_meta_data ->> 'role'
    else 'buyer'
  end,
  auth_user.created_at
from auth.users as auth_user
where auth_user.email is not null
on conflict (id) do update
set email = excluded.email;

create or replace function public.create_profile_for_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, email, role)
  values (
    new.id,
    lower(new.email),
    case
      when new.raw_user_meta_data ->> 'role' in ('buyer', 'shop')
        then new.raw_user_meta_data ->> 'role'
      else 'buyer'
    end
  )
  on conflict (id) do update
  set email = excluded.email;
  return new;
end;
$$;

drop trigger if exists create_profile_after_auth_user_insert on auth.users;
create trigger create_profile_after_auth_user_insert
after insert on auth.users
for each row execute function public.create_profile_for_auth_user();

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
     and (select relrowsecurity from pg_class where oid = 'public.profiles'::regclass)
     and (select relrowsecurity from pg_class where oid = 'public.shops'::regclass)
     and (
       select relrowsecurity
       from pg_class
       where oid = 'public.inventory_items'::regclass
     )
     and has_table_privilege('anon', 'public.shops', 'select')
     and has_table_privilege('anon', 'public.inventory_items', 'select');
$$;
grant execute on function public.backend_readiness() to anon, authenticated;

do $$
declare
  constraint_row record;
begin
  if to_regclass('public.legacy_users') is not null then
    for constraint_row in
      select conname
      from pg_constraint
      where conrelid = 'public.shops'::regclass
        and confrelid = 'public.legacy_users'::regclass
    loop
      execute format('alter table public.shops drop constraint %I', constraint_row.conname);
    end loop;

    update public.shops as shop
    set owner_id = auth_user.id
    from public.legacy_users as legacy_user
    join auth.users as auth_user
      on lower(auth_user.email) = lower(legacy_user.email)
    where shop.owner_id = legacy_user.id;

    if exists (
      select 1
      from public.shops as shop
      left join auth.users as auth_user on auth_user.id = shop.owner_id
      where auth_user.id is null
    ) then
      raise exception
        'Some existing shops have no matching Supabase Auth user. Create matching Auth accounts and retry this migration.';
    end if;
  end if;
end
$$;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'shops_owner_id_auth_fkey'
      and conrelid = 'public.shops'::regclass
  ) then
    alter table public.shops
      add constraint shops_owner_id_auth_fkey
      foreign key (owner_id) references auth.users (id) on delete cascade;
  end if;
end
$$;

alter table public.profiles enable row level security;
alter table public.shops enable row level security;
alter table public.inventory_items enable row level security;

revoke all on public.profiles from anon, authenticated;
revoke all on public.shops from anon, authenticated;
revoke all on public.inventory_items from anon, authenticated;
grant select on public.profiles to authenticated;
grant select on public.shops to anon, authenticated;
grant insert, update, delete on public.shops to authenticated;
grant select on public.inventory_items to anon, authenticated;
grant insert, update, delete on public.inventory_items to authenticated;

drop policy if exists profiles_read_self on public.profiles;
create policy profiles_read_self
on public.profiles for select to authenticated
using ((select auth.uid()) = id);

drop policy if exists shops_public_read on public.shops;
drop policy if exists shops_owner_insert on public.shops;
drop policy if exists shops_owner_update on public.shops;
drop policy if exists shops_owner_delete on public.shops;
create policy shops_public_read
on public.shops for select to anon, authenticated
using (true);
create policy shops_owner_insert
on public.shops for insert to authenticated
with check ((select auth.uid()) = owner_id);
create policy shops_owner_update
on public.shops for update to authenticated
using ((select auth.uid()) = owner_id)
with check ((select auth.uid()) = owner_id);
create policy shops_owner_delete
on public.shops for delete to authenticated
using ((select auth.uid()) = owner_id);

drop policy if exists inventory_live_read on public.inventory_items;
drop policy if exists inventory_owner_insert on public.inventory_items;
drop policy if exists inventory_owner_update on public.inventory_items;
drop policy if exists inventory_owner_delete on public.inventory_items;
create policy inventory_live_read
on public.inventory_items for select to anon, authenticated
using (is_active and quantity > 0);
create policy inventory_owner_insert
on public.inventory_items for insert to authenticated
with check (
  exists (
    select 1 from public.shops
    where shops.id = inventory_items.shop_id
      and shops.owner_id = (select auth.uid())
  )
);
create policy inventory_owner_update
on public.inventory_items for update to authenticated
using (
  exists (
    select 1 from public.shops
    where shops.id = inventory_items.shop_id
      and shops.owner_id = (select auth.uid())
  )
)
with check (
  exists (
    select 1 from public.shops
    where shops.id = inventory_items.shop_id
      and shops.owner_id = (select auth.uid())
  )
);
create policy inventory_owner_delete
on public.inventory_items for delete to authenticated
using (
  exists (
    select 1 from public.shops
    where shops.id = inventory_items.shop_id
      and shops.owner_id = (select auth.uid())
  )
);

do $$
begin
  if to_regclass('public.legacy_users') is not null then
    alter table public.legacy_users enable row level security;
    revoke all on public.legacy_users from anon, authenticated;
  end if;
end
$$;

notify pgrst, 'reload schema';

commit;
