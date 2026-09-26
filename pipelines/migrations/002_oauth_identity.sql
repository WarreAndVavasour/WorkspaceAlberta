-- workspaceAlberta OAuth 2.1 identity + per-user profile/watchlist storage.
-- Apply in the Supabase SQL editor after 001_create_wa_subscribers.sql.
-- The hosted server reads/writes these tables with the service-role key only.
-- Project region: Toronto (ca-central-1). Do not move this to a US region.

create table if not exists public.wa_users (
    id uuid primary key default gen_random_uuid(),
    email text unique not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.wa_user_data (
    user_id uuid primary key references public.wa_users (id) on delete cascade,
    profile jsonb not null default '{}'::jsonb,
    watchlist jsonb not null default '[]'::jsonb,
    updated_at timestamptz not null default now()
);

create table if not exists public.wa_oauth_clients (
    client_id text primary key,
    client_name text not null default '',
    redirect_uris jsonb not null,
    token_endpoint_auth_method text not null default 'none',
    client_id_issued_at bigint not null,
    grant_types jsonb not null default '["authorization_code","refresh_token"]'::jsonb,
    response_types jsonb not null default '["code"]'::jsonb
);

create table if not exists public.wa_oauth_auth_codes (
    code_hash text primary key,
    client_id text not null,
    redirect_uri text not null,
    code_challenge text not null,
    resource text not null,
    user_email text not null,
    user_id text not null,
    scope text not null default 'pro',
    expires_at timestamptz not null,
    consumed_at timestamptz
);

create table if not exists public.wa_oauth_refresh_tokens (
    token_hash text primary key,
    client_id text not null,
    user_email text not null,
    user_id text not null,
    resource text not null,
    scope text not null default 'pro offline_access',
    expires_at timestamptz not null,
    revoked_at timestamptz
);

create table if not exists public.wa_oauth_login_challenges (
    id text primary key,
    email text not null,
    code_hash text not null,
    authorize_params jsonb not null,
    expires_at timestamptz not null,
    attempts int not null default 0,
    consumed_at timestamptz
);

create index if not exists wa_subscribers_email_idx
    on public.wa_subscribers (lower(email));

create index if not exists wa_oauth_refresh_client_idx
    on public.wa_oauth_refresh_tokens (client_id);

drop trigger if exists wa_users_touch on public.wa_users;
create trigger wa_users_touch
    before update on public.wa_users
    for each row execute function public.wa_touch_updated_at();

drop trigger if exists wa_user_data_touch on public.wa_user_data;
create trigger wa_user_data_touch
    before update on public.wa_user_data
    for each row execute function public.wa_touch_updated_at();

alter table public.wa_users enable row level security;
alter table public.wa_user_data enable row level security;
alter table public.wa_oauth_clients enable row level security;
alter table public.wa_oauth_auth_codes enable row level security;
alter table public.wa_oauth_refresh_tokens enable row level security;
alter table public.wa_oauth_login_challenges enable row level security;

revoke all on public.wa_users from anon, authenticated;
revoke all on public.wa_user_data from anon, authenticated;
revoke all on public.wa_oauth_clients from anon, authenticated;
revoke all on public.wa_oauth_auth_codes from anon, authenticated;
revoke all on public.wa_oauth_refresh_tokens from anon, authenticated;
revoke all on public.wa_oauth_login_challenges from anon, authenticated;
