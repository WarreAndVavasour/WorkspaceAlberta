#!/usr/bin/env python3
"""Build an allowlisted OpenAI ZIP; probe without credentials or write actions.

Local checks do not constitute an OpenAI scan, approval, or publication.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import struct
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'plugins/workspacealberta'
ORIGIN = 'https://elbowsupknivesout.warreandvavasour.com'
FILES = ('plugin.json', 'mcp.json', 'skills/procurement/SKILL.md',
         'skills/procurement/requirements-board.html', 'assets/icon.png')


def validate(package: Path = PACKAGE) -> dict:
    actual = {str(p.relative_to(package)) for p in package.rglob('*') if p.is_file() or p.is_symlink()}
    if actual != set(FILES) or any(p.is_symlink() for p in package.rglob('*')):
        raise ValueError('Package must contain exactly the allowlisted files, without symlinks.')
    manifest = json.loads((package / 'plugin.json').read_text())
    if manifest.get('name') != 'workspacealberta' or not re.fullmatch(r'\d+\.\d+\.\d+', manifest.get('version', '')):
        raise ValueError('Invalid package identity or version.')
    interface = manifest['extensions']['com.openai']['interface']
    for field, bound in [('displayName',30),('shortDescription',30),('longDescription',4000),('developerName',80)]:
        if not isinstance(interface.get(field),str) or not 0 < len(interface[field]) <= bound:
            raise ValueError('Invalid '+field)
    prompts=interface['defaultPrompt']
    if not 1 <= len(prompts) <= 3 or any(not isinstance(p,str) or not 0<len(p)<=128 for p in prompts):
        raise ValueError('Invalid defaultPrompt')
    for field in ('websiteURL','supportURL','privacyPolicyURL','termsOfServiceURL'):
        if (urlparse(interface[field]).scheme != 'https' or urlparse(interface[field]).netloc != urlparse(ORIGIN).netloc or urlparse(interface[field]).fragment):
            raise ValueError('Unexpected publisher URL')
    if interface['composerIcon'] != './assets/icon.png' or interface['logo'] != './assets/icon.png':
        raise ValueError('Invalid asset path')
    mcp=json.loads((package/'mcp.json').read_text())
    if mcp['mcpServers'] != {'workspacealberta': {'type':'streamable-http','url':ORIGIN+'/mcp'}}:
        raise ValueError('Unexpected MCP endpoint or credentials in MCP configuration')
    skill=(package/'skills/procurement/SKILL.md').read_text()
    if not skill.startswith('---\nname: procurement\ndescription: ') or '\n---\n' not in skill[4:]:
        raise ValueError('Missing skill frontmatter')
    if '${user_config.' in skill or 'wa_live_' in skill:
        raise ValueError('Unsupported installation variables or credential examples')
    icon=(package/'assets/icon.png').read_bytes()
    if icon[:8]!=b'\x89PNG\r\n\x1a\n' or not 48 <= struct.unpack('>II',icon[16:24])[0] <=4096:
        raise ValueError('Invalid icon')
    w,h=struct.unpack('>II',icon[16:24])
    if w!=h or len(icon)>5*1024*1024:
        raise ValueError('Icon must be square and under 5 MiB')
    return {'version':manifest['version'],'files':list(FILES),'validation':'local checks only; portal scan still required'}


def build(output: Path, package: Path = PACKAGE) -> dict:
    report=validate(package)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            archive.writestr(info,(package/name).read_bytes())
    report['sha256']=hashlib.sha256(output.read_bytes()).hexdigest()
    report['bytes']=output.stat().st_size
    return report


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe(base_url: str = ORIGIN) -> dict:
    # Only our public origin and our exact tagged Cloud Run service may be probed.
    parsed = urlparse(base_url)
    stage_host = r"[a-z][a-z0-9-]*---workspacealberta-b7gk5pch5q-nn\.a\.run\.app"
    if (parsed.scheme != 'https' or parsed.path not in ('', '/') or parsed.query
            or parsed.fragment or parsed.username or parsed.password
            or not (parsed.netloc == urlparse(ORIGIN).netloc or re.fullmatch(stage_host, parsed.netloc))):
        raise ValueError('Probe target must be the production origin or a tag of this Cloud Run service')
    base_url = base_url.rstrip('/')
    checks=[]
    headers={'Accept':'application/json, text/event-stream','User-Agent':'WorkspaceAlberta-OpenAI-Readiness/1.0'}
    opener=build_opener(NoRedirects())
    def request(path,payload=None):
        h=dict(headers)
        if payload is not None: h['Content-Type']='application/json'
        req=Request(base_url+path,headers=h,data=json.dumps(payload).encode() if payload is not None else None)
        try:
            with opener.open(req,timeout=25) as res:
                raw=res.read(2*1024*1024+1)
                if len(raw)>2*1024*1024: raise ValueError('Response exceeded safe size limit')
                return res.status,dict(res.headers),raw
        except HTTPError as exc: return exc.code,dict(exc.headers),b''
    def decoded(raw):
        if not raw: return {}
        if raw.lstrip().startswith(b'data:') or b'\ndata:' in raw:
            payloads=[line[5:].strip() for line in raw.splitlines() if line.startswith(b'data:')]
            return json.loads(payloads[-1])
        return json.loads(raw)
    def check(name,run):
        try:
            ok,detail=run();checks.append({'name':name,'pass':bool(ok),'detail':detail})
        except Exception as exc:
            checks.append({'name':name,'pass':False,'error':type(exc).__name__,'detail':'Probe could not complete; not proof the service is down.'})
    def http(path,expected):
        status,_,_=request(path)
        return status==expected,{'status':status,'expected':expected}
    for path in ('/health','/support','/privacy','/terms'):
        check(path,lambda p=path:http(p,200))
    for path in ('/.well-known/oauth-authorization-server','/.well-known/openid-configuration'):
        def metadata(p=path):
            status,_,raw=request(p);data=decoded(raw)
            ok=(status==200 and data.get('issuer')==ORIGIN and {'openid','email'}.issubset(data.get('scopes_supported',[])) and data.get('userinfo_endpoint')==ORIGIN+'/userinfo' and data.get('authorization_response_iss_parameter_supported') is True)
            return ok,{'status':status,'scopes':data.get('scopes_supported',[]),'userinfo_endpoint':data.get('userinfo_endpoint')}
        check(path,metadata)
    check('userinfo rejects anonymous access',lambda:http('/userinfo',401))
    def challenge():
        status,h,raw=request('/.well-known/openai-apps-challenge')
        content_type=next((v for k,v in h.items() if k.lower()=='content-type'),'')
        return status==200 and bool(raw) and content_type.startswith('text/plain'),{'status':status,'note':'HTTP 200 does not prove portal token matching or verified ownership.'}
    check('domain challenge configured',challenge)
    def rpc(method,params=None,request_id=1):
        body={'jsonrpc':'2.0','method':method}
        if request_id is not None:body['id']=request_id
        if params is not None:body['params']=params
        status,h,raw=request('/mcp',body)
        session=next((v for k,v in h.items() if k.lower()=='mcp-session-id'),None)
        if session:headers['Mcp-Session-Id']=session
        return status,decoded(raw)
    def initialize():
        status,body=rpc('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'workspacealberta-readiness','version':'1.0.0'}})
        result=body.get('result',{})
        if result.get('protocolVersion'):headers['MCP-Protocol-Version']=result['protocolVersion']
        ok=status==200 and bool(result.get('protocolVersion')) and not body.get('error')
        if ok:rpc('notifications/initialized',request_id=None)
        return ok,{'status':status,'protocolVersion':result.get('protocolVersion')}
    check('MCP initialize',initialize)
    def tools():
        status,body=rpc('tools/list',request_id=2)
        declared=body.get('result',{}).get('tools',[])
        missing=[t['name'] for t in declared if not t.get('securitySchemes') or not all(isinstance(t.get('annotations',{}).get(k),bool) for k in ('readOnlyHint','destructiveHint','openWorldHint'))]
        cursor=body.get('result',{}).get('nextCursor')
        return status==200 and bool(declared) and not missing and not cursor,{'status':status,'count':len(declared),'missing_metadata':missing,'pagination_remaining':bool(cursor)}
    check('MCP tool declarations',tools)
    def guide():
        status,body=rpc('tools/call',{'name':'get_server_guide','arguments':{}},3)
        result=body.get('result',{})
        return status==200 and bool(result.get('content')) and not result.get('isError') and not body.get('error'),{'status':status}
    check('public guide',guide)
    def protected():
        status,body=rpc('tools/call',{'name':'get_my_profile','arguments':{}},4)
        result=body.get('result',{})
        return status==401 or (result.get('isError') is True and bool(result.get('_meta',{}).get('mcp/www_authenticate'))),{'status':status}
    check('private profile rejects anonymous access',protected)
    return {'checked_at':datetime.now(timezone.utc).isoformat(),'endpoint':base_url+'/mcp','canonical_resource':ORIGIN+'/mcp','backend_checks_pass':all(c['pass'] for c in checks if c['name'] not in ('/terms','domain challenge configured')),'technical_checks_pass':all(c['pass'] for c in checks),'checks':checks,'not_tested':['Authenticated Google sign-in and token refresh in OpenAI','All reviewer scenarios','Portal token equality and verified identity','OpenAI scan, review, approval and publication']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['build','probe','validate'])
    parser.add_argument('--output',type=Path)
    parser.add_argument('--require-ready',action='store_true')
    parser.add_argument('--require-backend',action='store_true')
    parser.add_argument('--base-url',default=ORIGIN)
    args=parser.parse_args()
    if args.command=='build':report=build(args.output or ROOT/'output/openai/workspacealberta-openai.zip')
    elif args.command=='validate':report=validate()
    else:
        report=probe(args.base_url)
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if args.require_backend and not report.get('backend_checks_pass',False):return 1
    if args.require_ready and not report.get('technical_checks_pass',False):return 1
    return 0

if __name__=='__main__':sys.exit(main())
