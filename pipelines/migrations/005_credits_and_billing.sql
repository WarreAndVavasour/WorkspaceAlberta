-- Phase 1 monetization: 2 free Pro trial credits per signed-in account,
-- pay-per-tender Bid Pack credits, and user_id-linked Stripe billing.
-- Apply in the Supabase SQL editor after 004_google_login.sql.
-- Safe to deploy code before applying: storage.py gracefully falls back when
-- these columns are not yet present.

begin;

alter table public.wa_user_data
    add column if not exists free_credits_used int not null default 0,
    add column if not exists paid_credits int not null default 0,
    add column if not exists stripe_customer_id text not null default '',
    add column if not exists credited_sessions jsonb not null default '[]'::jsonb;

alter table public.wa_subscribers
    add column if not exists user_id uuid references public.wa_users (id) on delete set null;

create index if not exists wa_subscribers_user_id_idx
    on public.wa_subscribers (user_id)
    where user_id is not null;

create index if not exists wa_user_data_stripe_customer_idx
    on public.wa_user_data (stripe_customer_id)
    where stripe_customer_id <> '';

commit;
