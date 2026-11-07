-- Run sql/001_init.sql first. This migration validates new data requirements
-- only after legacy rows have been reviewed and cleaned up.
--
-- Find rows that need attention before running this migration:
--   select id, name, location, county from public.shops
--   where location is null or location !~ '[^[:space:]]'
--      or county is null or county !~ '[^[:space:]]';
--   select id, county from public.shops
--   where lower(replace(btrim(county), '-', ' ')) not in (
--     'baringo', 'bomet', 'bungoma', 'busia', 'elgeyo marakwet', 'embu',
--     'garissa', 'homa bay', 'isiolo', 'kajiado', 'kakamega', 'kericho',
--     'kiambu', 'kilifi', 'kirinyaga', 'kisii', 'kisumu', 'kitui', 'kwale',
--     'laikipia', 'lamu', 'machakos', 'makueni', 'mandera', 'marsabit',
--     'meru', 'migori', 'mombasa', 'murang''a', 'nakuru', 'nandi', 'narok',
--     'nyamira', 'nyandarua', 'nyeri', 'samburu', 'siaya', 'taita taveta',
--     'tana river', 'tharaka nithi', 'trans nzoia', 'turkana', 'uasin gishu',
--     'vihiga', 'wajir', 'west pokot', 'nairobi'
--   );
--   select id, name from public.inventory_items
--   where name !~ '[^[:space:]]'
--      or cardinality(regexp_split_to_array(btrim(name), E'\\s+')) > 20;
--   select owner_id, count(*) from public.shops
--   group by owner_id having count(*) > 1;
--
-- Do not remove duplicate shops automatically; decide which records to retain.

begin;

do $$
begin
  if exists (
    select 1 from public.shops
    where location is null or location !~ '[^[:space:]]'
       or county is null or county !~ '[^[:space:]]'
  ) then
    raise exception 'Fill in location and county for every existing shop before applying this migration';
  end if;

  if exists (
    select 1 from public.shops
    where lower(replace(btrim(county), '-', ' ')) not in (
      'baringo', 'bomet', 'bungoma', 'busia', 'elgeyo marakwet', 'embu',
      'garissa', 'homa bay', 'isiolo', 'kajiado', 'kakamega', 'kericho',
      'kiambu', 'kilifi', 'kirinyaga', 'kisii', 'kisumu', 'kitui', 'kwale',
      'laikipia', 'lamu', 'machakos', 'makueni', 'mandera', 'marsabit',
      'meru', 'migori', 'mombasa', 'murang''a', 'nakuru', 'nandi', 'narok',
      'nyamira', 'nyandarua', 'nyeri', 'samburu', 'siaya', 'taita taveta',
      'tana river', 'tharaka nithi', 'trans nzoia', 'turkana', 'uasin gishu',
      'vihiga', 'wajir', 'west pokot', 'nairobi'
    )
  ) then
    raise exception 'Correct county names to a supported Kenyan county before applying this migration';
  end if;

  if exists (
    select 1 from public.inventory_items
    where name !~ '[^[:space:]]'
       or cardinality(regexp_split_to_array(btrim(name), E'\\s+')) > 20
  ) then
    raise exception 'Rename or remove inventory descriptions longer than 20 words before applying this migration';
  end if;

  if exists (
    select 1 from public.shops
    group by owner_id
    having count(*) > 1
  ) then
    raise exception 'Resolve duplicate shops per owner before applying this migration';
  end if;
end
$$;

update public.shops
set county = case lower(replace(btrim(county), '-', ' '))
  when 'elgeyo marakwet' then 'Elgeyo-Marakwet'
  when 'murang''a' then 'Murang''a'
  when 'taita taveta' then 'Taita-Taveta'
  when 'tharaka nithi' then 'Tharaka-Nithi'
  else initcap(btrim(county))
end;

alter table public.shops drop constraint if exists shops_location_required;
alter table public.shops
  add constraint shops_location_required
  check (location is not null and location ~ '[^[:space:]]') not valid;
alter table public.shops drop constraint if exists shops_county_required;
alter table public.shops
  add constraint shops_county_required
  check (county is not null and county ~ '[^[:space:]]') not valid;
alter table public.inventory_items drop constraint if exists inventory_name_max_20_words;
alter table public.inventory_items
  add constraint inventory_name_max_20_words
  check (
    name ~ '[^[:space:]]'
    and cardinality(regexp_split_to_array(btrim(name), E'\\s+')) <= 20
  ) not valid;

alter table public.shops alter column location set not null;
alter table public.shops alter column county set not null;
alter table public.shops validate constraint shops_location_required;
alter table public.shops validate constraint shops_county_required;
alter table public.shops validate constraint shops_county_known;
alter table public.inventory_items validate constraint inventory_name_max_20_words;

create unique index if not exists shops_owner_id_unique_idx on public.shops (owner_id);
drop index if exists public.shops_owner_id_idx;

commit;
