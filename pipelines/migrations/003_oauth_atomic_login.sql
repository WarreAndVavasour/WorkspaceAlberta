-- Apply after 002_oauth_identity.sql. Serializes OTP attempts and consumption
-- across all Cloud Run instances. Other grants use conditional UPDATE RETURNING.
create or replace function public.wa_oauth_verify_login(p_id text, p_code_hash text)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
    challenge public.wa_oauth_login_challenges%rowtype;
    failure text;
begin
    select * into challenge from public.wa_oauth_login_challenges
        where id = p_id for update;
    if not found then
        failure := 'Sign-in challenge not found.';
    elsif challenge.consumed_at is not null then
        failure := 'Sign-in challenge already used.';
    elsif challenge.code_hash = encode(sha256('consent'::bytea), 'hex') then
        failure := 'Sign-in challenge not found.';
    elsif challenge.expires_at < clock_timestamp() then
        failure := 'Sign-in code expired. Start again.';
    elsif challenge.attempts >= 5 then
        failure := 'Too many attempts. Start again.';
    elsif challenge.code_hash <> p_code_hash or p_code_hash is null then
        update public.wa_oauth_login_challenges set attempts = attempts + 1 where id = p_id;
        failure := 'That code is incorrect.';
    else
        update public.wa_oauth_login_challenges set consumed_at = clock_timestamp() where id = p_id;
        return jsonb_build_object('row', to_jsonb(challenge));
    end if;
    return jsonb_build_object('error', failure);
end;
$$;

revoke all on function public.wa_oauth_verify_login(text, text) from public, anon, authenticated;
grant execute on function public.wa_oauth_verify_login(text, text) to service_role;
notify pgrst, 'reload schema';
