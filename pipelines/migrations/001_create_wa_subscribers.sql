-- WorkspaceAlberta Pro subscribers: API-key auth + tenant storage.
-- Apply in the Supabase SQL editor (or via `supabase db push`).
-- The server reads/writes this table with the service-role key only.

create table if not exists public.wa_subscribers (
    key_hash text primary key,                 -- sha256 of the wa_live_ API key
    stripe_customer_id text unique not null,
    email text not null default '',
    status text not null default 'active' check (status in ('active', 'cancelled', 'past_due')),
    plan text not null default 'pro',
    pending_key text,                          -- plaintext key held only until delivered to the customer
    profile jsonb not null default '{}'::jsonb,
    watchlist jsonb not null default '[]'::jsonb,
    bid_rooms_used_month int not null default 0,
    bid_rooms_month text not null default '',  -- e.g. '2026-07', reset marker
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists wa_subscribers_stripe_customer_idx
    on public.wa_subscribers (stripe_customer_id);
create index if not exists wa_subscribers_status_idx
    on public.wa_subscribers (status);

create or replace function public.wa_touch_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists wa_subscribers_touch on public.wa_subscribers;
create trigger wa_subscribers_touch
    before update on public.wa_subscribers
    for each row execute function public.wa_touch_updated_at();

-- Service-role only: no anon/authenticated access.
alter table public.wa_subscribers enable row level security;
revoke all on public.wa_subscribers from anon, authenticated;
