-- Upstream Google sign-in. MCP tokens and the existing issuer stay unchanged.
begin;
alter table public.wa_users add column if not exists google_subject text unique;

create table if not exists public.wa_oauth_google_states (
    state_hash text primary key,
    browser_hash text not null,
    nonce text not null,
    code_verifier text not null,
    authorize_params jsonb not null,
    expires_at timestamptz not null,
    consumed_at timestamptz
);
alter table public.wa_oauth_google_states enable row level security;
revoke all on public.wa_oauth_google_states from anon, authenticated;
grant all on public.wa_oauth_google_states to service_role;
create index if not exists wa_oauth_google_states_expiry on public.wa_oauth_google_states(expires_at);

-- The unique constraints settle concurrent first sign-ins. Never merge an
-- existing email account into a Google identity without a separate link flow.
create or replace function public.wa_google_user(p_subject text, p_email text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare u public.wa_users;
begin
    if p_subject is null or length(p_subject) not between 1 and 255
       or p_email is null or position('@' in p_email) < 2 then
        raise exception 'Invalid Google identity';
    end if;
    begin
        insert into public.wa_users(email, google_subject)
        values (lower(trim(p_email)), p_subject)
        on conflict (google_subject) do update
        set email = excluded.email, updated_at = now()
        returning * into u;
    exception when unique_violation then
        return jsonb_build_object('error', 'account_link_required');
    end;
    return jsonb_build_object('id', u.id, 'email', u.email, 'google_subject', u.google_subject);
end;
$$;
revoke all on function public.wa_google_user(text, text) from public, anon, authenticated;
grant execute on function public.wa_google_user(text, text) to service_role;
commit;
