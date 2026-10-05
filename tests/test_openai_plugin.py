"""OpenAI package and OAuth interoperability regressions; no live accounts."""
from __future__ import annotations
import hashlib
import importlib.util
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from scripts import openai_plugin as package

class PackageTest(unittest.TestCase):
    def test_package_has_mcp_and_skill(self):
        self.assertIn('mcp.json', package.validate()['files'])
        self.assertIn('skills/procurement/SKILL.md', package.validate()['files'])

    def test_build_is_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            a=package.build(Path(directory)/'a.zip')
            b=package.build(Path(directory)/'b.zip')
            self.assertEqual(a['sha256'],b['sha256'])

    def test_unexpected_secret_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'plugin';shutil.copytree(package.PACKAGE,root)
            (root/'.env').write_text('DO_NOT_SHIP=fixture')
            with self.assertRaises(ValueError): package.validate(root)

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'plugin';shutil.copytree(package.PACKAGE,root)
            icon=root/'assets/icon.png';icon.unlink();icon.symlink_to(package.PACKAGE/'assets/icon.png')
            with self.assertRaises(ValueError): package.validate(root)

@unittest.skipIf(importlib.util.find_spec('mcp') is None, 'MCP dependencies unavailable locally; required in CI')
class OpenAIInteropTest(unittest.TestCase):
    def setUp(self):
        from procurement_core import oauth, identity
        from procurement_core.openai_support import STABLE_CALLBACK
        from tests.test_procurement_http_app import app
        from fastapi.testclient import TestClient
        self.oauth=oauth;self.identity=identity
        self.env=patch.dict(os.environ,{'WA_OAUTH_STORE':'memory','WA_LOGIN_PROVIDER':'email',
            'WA_OAUTH_DEV_SHOW_CODE':'1','WA_HOSTED':'1','CANADABUYS_LOAD_ENV_FILE':'0',
            'WA_OPENAI_REDIRECT_URIS':'','WA_OPENAI_APPS_CHALLENGE':''})
        self.env.start();self.addCleanup(self.env.stop)
        oauth.reset_oauth_state();self.addCleanup(oauth.reset_oauth_state)
        self.store=oauth.MemoryOAuthStore();oauth.use_store(self.store)
        self.addCleanup(oauth.use_store,None)
        identity.set_subscriber_lookup(lambda _email:None)
        self.addCleanup(identity.set_subscriber_lookup,None)
        self.http=TestClient(app);self.http.__enter__()
        self.addCleanup(self.http.__exit__,None,None,None)
        self.redirect=STABLE_CALLBACK
        self.client=oauth.register_client({'client_name':'OpenAI test','redirect_uris':[self.redirect]})
        self.verifier='a'*64
        self.params=oauth.validate_authorize_params({'response_type':'code',
            'client_id':self.client['client_id'],'redirect_uri':self.redirect,
            'code_challenge':oauth._b64url(hashlib.sha256(self.verifier.encode()).digest()),
            'code_challenge_method':'S256','resource':oauth.public_mcp_resource(),
            'scope':'pro openid email','state':'state-fixture'})
        self.user=self.store.upsert_user('review@example.com')

    def tokens(self):
        code=self.oauth.issue_authorization_code(self.user,self.params)
        return self.oauth.issue_tokens({'grant_type':'authorization_code','code':code,
            'client_id':self.client['client_id'],'redirect_uri':self.redirect,
            'code_verifier':self.verifier,'resource':self.oauth.public_mcp_resource()})

    def info(self,token):
        return self.http.get('/userinfo',headers={'Authorization':'Bearer '+token})

    def test_discovery_exposes_enabled_identity_scopes(self):
        for path in ('/.well-known/openid-configuration','/.well-known/oauth-authorization-server'):
            data=self.http.get(path).json()
            self.assertTrue({'openid','email','pro'}.issubset(data['scopes_supported']))
            self.assertEqual(data['userinfo_endpoint'],self.oauth.public_origin()+'/userinfo')
            self.assertIs(data['authorization_response_iss_parameter_supported'],True)

    def test_exact_callback_allowlist_and_claude_compatibility(self):
        for uri in (self.redirect,'https://claude.ai/api/mcp/auth_callback','http://localhost:9999/callback'):
            self.assertTrue(self.oauth.redirect_uri_allowed(uri))
        for uri in (self.redirect+'?evil=1',self.redirect+'#fragment',self.redirect+'/',
                    self.redirect.replace('chatgpt.com','chatgpt.com.evil.test'),
                    'https://chatgpt.com/connector/oauth/unconfigured','https://attacker.test/callback'):
            self.assertFalse(self.oauth.redirect_uri_allowed(uri),uri)

    def test_callback_id_requires_exact_configuration(self):
        uri='https://chatgpt.com/connector/oauth/review-123'
        with patch.dict(os.environ,{'WA_OPENAI_REDIRECT_URIS':uri+',https://evil.test/callback'}):
            self.assertTrue(self.oauth.redirect_uri_allowed(uri))
            self.assertFalse(self.oauth.redirect_uri_allowed(uri+'-other'))
            self.assertFalse(self.oauth.redirect_uri_allowed('https://evil.test/callback'))

    def test_success_and_error_callbacks_echo_exact_issuer(self):
        from procurement_core.oauth_http import _error_redirect
        for target in (self.oauth.authorization_redirect(self.params,'code'),
            _error_redirect(self.redirect,'access_denied','Denied','state-fixture')):
            query=parse_qs(urlparse(target).query)
            self.assertEqual(query['iss'],[self.oauth.public_origin()])
            self.assertEqual(query['state'],['state-fixture'])

    def test_unknown_scope_is_rejected(self):
        from procurement_core.oauth import OAuthError
        with self.assertRaises(OAuthError):
            self.oauth.validate_authorize_params({**self.params,'scope':'openid admin'})

    def test_verified_login_grant_returns_minimal_userinfo(self):
        result=self.info(self.tokens()['access_token'])
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json(),{'sub':self.user['id'],'email':self.user['email'],'email_verified':True})
        self.assertEqual(result.headers['cache-control'],'no-store')

    def test_real_otp_proof_chain_and_refresh_preserve_identity(self):
        with patch.object(self.oauth,'send_login_code',return_value=True):
            started=self.oauth.start_login('proof@example.com',self.params)
        verified=self.oauth.verify_login(started['login_id'],started['dev_code'])
        consent=self.oauth.take_consent(verified['consent_id'])
        self.user=consent['user']
        initial=self.tokens()
        renewed=self.oauth.issue_tokens({'grant_type':'refresh_token','refresh_token':initial['refresh_token'],
                                        'client_id':self.client['client_id']})
        self.assertEqual(self.info(initial['access_token']).json(),self.info(renewed['access_token']).json())
        self.assertIs(self.info(renewed['access_token']).json()['email_verified'],True)

    def test_userinfo_requires_oauth_not_legacy_key_or_query_token(self):
        self.assertEqual(self.http.get('/userinfo').status_code,401)
        self.assertEqual(self.info('wa_live_fixture').status_code,401)
        self.assertEqual(self.info('wa_at_invalid').status_code,401)
        self.assertEqual(self.http.get('/userinfo?access_token='+self.tokens()['access_token']).status_code,401)

    def test_userinfo_requires_email_scope(self):
        token=self.oauth._mint_access_token({**self.user,'email_verified':True},self.oauth.public_mcp_resource(),'pro')
        self.assertEqual(self.info(token).status_code,403)

    def test_userinfo_does_not_invent_verified_status(self):
        token=self.oauth._mint_access_token(self.user,self.oauth.public_mcp_resource(),'pro openid email')
        self.assertEqual(self.info(token).status_code,403)

    def test_userinfo_rejects_deleted_or_changed_account(self):
        token=self.tokens()['access_token'];self.store.users[self.user['id']]['email']='changed@example.com'
        self.assertEqual(self.info(token).status_code,401)
        self.store.users.clear()
        self.assertEqual(self.info(token).status_code,401)

    def test_userinfo_rejects_expired_token_and_wrong_audience(self):
        token=self.tokens()['access_token']
        with patch('procurement_core.oauth.time.time',return_value=time.time()+2000):
            self.assertEqual(self.info(token).status_code,401)
        token=self.oauth._mint_access_token({**self.user,'email_verified':True},'https://other.test/mcp','openid email')
        self.assertEqual(self.info(token).status_code,401)

    def test_identity_only_scopes_cannot_access_procurement_account(self):
        from procurement_core.auth import GateError
        token=self.oauth._mint_access_token({**self.user,'email_verified':True},self.oauth.public_mcp_resource(),'openid email')
        with self.assertRaises(GateError):
            self.identity.check_tool_access('get_my_profile','Bearer '+token)
        self.assertIsNone(self.identity.check_tool_access('find_matching_opportunities','Bearer '+token))

    def test_domain_challenge_exact_bytes_and_unconfigured_404(self):
        self.assertEqual(self.http.get('/.well-known/openai-apps-challenge').status_code,404)
        with patch.dict(os.environ,{'WA_OPENAI_APPS_CHALLENGE':'test.exact-token'}):
            response=self.http.get('/.well-known/openai-apps-challenge')
            self.assertEqual(response.content,b'test.exact-token')
            self.assertTrue(response.headers['content-type'].startswith('text/plain'))
            self.assertEqual(response.headers['cache-control'],'no-store')

    def test_tools_have_explicit_auth_and_action_metadata(self):
        from mcp_tools import get_mcp_tools
        from procurement_core.auth import PRO_TOOLS,SIGN_IN_TOOLS
        for tool in get_mcp_tools():
            wire=tool.model_dump(by_alias=True,exclude_none=True)
            self.assertEqual(wire['securitySchemes'],wire['_meta']['securitySchemes'])
            if tool.name in PRO_TOOLS|SIGN_IN_TOOLS:
                self.assertEqual(wire['securitySchemes'],[{'type':'oauth2','scopes':['pro']}])
            else:self.assertIn({'type':'noauth'},wire['securitySchemes'])
            for hint in ('readOnlyHint','destructiveHint','openWorldHint'):
                self.assertIsInstance(wire['annotations'][hint],bool)
            if tool.name=='process_bid_room':self.assertFalse(wire['annotations']['readOnlyHint'])

    def test_tool_auth_error_contains_challenge_but_payment_error_does_not(self):
        import asyncio
        from mcp.types import CallToolRequestParams
        from procurement_core.auth import GateError
        from server_http import handle_call_tool
        for code in (401,402):
            with patch('server_http.check_tool_access',side_effect=GateError(code,'Access required')):
                result=asyncio.run(handle_call_tool(None,CallToolRequestParams(name='get_my_profile',arguments={})))
            wire=result.model_dump(by_alias=True,exclude_none=True)
            self.assertTrue(wire['isError'])
            if code==401:self.assertIn('mcp/www_authenticate',wire['_meta'])
            else:self.assertNotIn('mcp/www_authenticate',wire.get('_meta',{}))

if __name__=='__main__': unittest.main()
