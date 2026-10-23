-- Expenses table. The API validates every rule first; these constraints are a
-- second line of defence so bad rows can never reach the table.
-- "Not in the future" is enforced in the API only: it depends on the clock and
-- the configured timezone, which a CHECK constraint should not.
--
-- Names are unqualified on purpose: production runs it with the default
-- search_path (public); the test suite runs the same file with search_path=test.

create table if not exists expenses (
    id           bigint generated always as identity primary key,
    title        varchar(100) not null check (length(btrim(title)) > 0),
    amount       numeric(10, 2) not null check (amount > 0),
    category     text not null check (category in ('food', 'travel', 'bills', 'other')),
    expense_date date not null,
    created_at   timestamptz not null default now()
);

-- Matches the list ordering (newest first, stable tie-breakers) and date filters.
create index if not exists expenses_order_idx
    on expenses (expense_date desc, created_at desc, id desc);

-- Category filter and per-category monthly summary.
create index if not exists expenses_category_date_idx
    on expenses (category, expense_date desc);

-- The backend connects as the database owner, which bypasses RLS. Enabling RLS
-- with no policies blocks anon/authenticated access through Supabase's Data API.
alter table expenses enable row level security;
