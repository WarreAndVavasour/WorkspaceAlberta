"""Stage or promote an exact Cloud Run revision; never deploy an untracked tree.

Requires gcloud, git and the repository's Python dependencies. Does not print
runtime environment values or fetch secret payloads. See docs/deployment.md.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from html import escape
from xml.etree import ElementTree as ET

from verify_oauth_readiness import verify as verify_oauth
from verify_procurement_rollout import verify as verify_procurement

PROJECT = "workspacealberta-prod"
REGION = "northamerica-northeast1"
SERVICE = "workspacealberta"
ORIGIN = "https://elbowsupknivesout.warreandvavasour.com"
IMAGE = f"{REGION}-docker.pkg.dev/{PROJECT}/cloud-run-source-deploy/{SERVICE}"
CLIENT_METADATA = "https://claude.ai/oauth/claude-code-client-metadata"
ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def gcloud(*args):
    executable = shutil.which("gcloud.cmd") or shutil.which("gcloud")
    require(executable, "Install gcloud and authenticate first")
    result = subprocess.run([executable, *args, f"--project={PROJECT}",
                             f"--region={REGION}", "--quiet", "--format=json"],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def reviewed_commit(commit):
    require(re.fullmatch(r"[0-9a-f]{40}", commit), "Expected a full source commit SHA")
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "origin/main"],
                   cwd=ROOT, check=True, capture_output=True)
    return commit


def production_revision(service):
    traffic = [entry for entry in service["status"]["traffic"] if entry.get("percent", 0)]
    require(len(traffic) == 1 and traffic[0]["percent"] == 100,
            "Expected one explicit revision at 100% traffic; inspect split traffic manually")
    return traffic[0]["revisionName"]


def runtime_identity(spec):
    # Compare privately: this may contain old inline credentials; never serialize it.
    return {"account": spec.get("serviceAccountName"),
            "env": sorted(spec["containers"][0].get("env", []), key=lambda item: item["name"])}


def candidate(service, revision):
    require(re.fullmatch(r"workspacealberta-[a-z0-9-]{1,47}", revision), "Invalid revision name")
    details = gcloud("run", "revisions", "describe", revision)
    labels = details["metadata"].get("labels", {})
    require(labels.get("serving.knative.dev/service") == SERVICE, "Revision belongs to another service")
    require(any(c["type"] == "Ready" and c["status"] == "True"
                for c in details["status"].get("conditions", [])), "Revision is not ready")
    commit = reviewed_commit(labels.get("source-commit", ""))
    digest = details["status"].get("imageDigest", "")
    require(re.fullmatch(re.escape(IMAGE) + r"@sha256:[0-9a-f]{64}", digest),
            "Revision image must be an immutable digest from our Artifact Registry")
    urls = [t["url"] for t in service["status"]["traffic"]
            if t.get("revisionName") == revision and t.get("tag") and t.get("url")]
    require(urls, "Revision needs a traffic tag for verification before promotion")
    return {"revision": revision, "commit": commit, "image": digest, "url": urls[0]}, details


def verify_assets(url, commit):
    names = git("ls-tree", "-r", "--name-only", commit, "procurement_core/assets/archive").decode().splitlines()
    names = [name for name in names if name.endswith(".webp")]
    require(names, "Source commit contains no archive images")
    result = {}
    for name in names + ["procurement_core/assets/google-signin.png"]:
        path = "/assets/" + name.removeprefix("procurement_core/assets/")
        request = Request(url + path, headers={"User-Agent": "WorkspaceAlberta-Acceptance/1.0"})
        with urlopen(request, timeout=30) as response:
            body = response.read(2_000_001)
            require(response.status == 200, f"Asset unavailable: {path}")
            require(response.headers.get_content_type() == ("image/webp" if name.endswith(".webp") else "image/png"),
                    f"Wrong asset content type: {path}")
        require(hashlib.sha256(body).digest() == hashlib.sha256(git("show", f"{commit}:{name}")).digest(),
                f"Deployed asset differs from reviewed source: {path}")
        result[path] = hashlib.sha256(body).hexdigest()
    query = urlencode({"response_type": "code", "client_id": CLIENT_METADATA,
                       "redirect_uri": "http://localhost:3118/callback", "resource": ORIGIN + "/mcp",
                       "code_challenge_method": "S256", "code_challenge": "a" * 43,
                       "state": "release-check", "scope": "pro offline_access"})
    with urlopen(Request(url + "/authorize?" + query, headers={"User-Agent": "WorkspaceAlberta-Acceptance/1.0"}), timeout=30) as response:
        page = response.read(200_000).decode()
        require('action="/authorize/google"' in page and 'connection-card' in page,
                "Branded Google sign-in page is missing")
        require(all("/assets/archive/" + Path(name).name in page for name in names), "Sign-in collage is incomplete")
    return result


def verify(url, commit):
    print(f"Verifying {url}", flush=True)
    return {"oauth": verify_oauth(url, ORIGIN + "/mcp"),
            "assets": verify_assets(url, commit),
            "website": verify_website(url, commit),
            "procurement": asyncio.run(verify_procurement(url))}


def verify_website(url, commit):
    """Check packaged blog content and CSS against the exact reviewed commit."""
    paths = git("ls-tree", "-r", "--name-only", commit, "procurement_core/content/blog").decode().splitlines()
    if not paths:  # Allow promotion/rollback of revisions predating the blog.
        return {"blog": "not in this source commit"}

    def read(path):
        with urlopen(Request(url + path, headers={"User-Agent": "WorkspaceAlberta-Acceptance/1.0"}), timeout=15) as response:
            require(response.status == 200, f"Website route unavailable: {path}")
            return response.read(500_000)

    css = read("/assets/blog.css")
    require(hashlib.sha256(css).digest() == hashlib.sha256(git("show", f"{commit}:procurement_core/assets/blog.css")).digest(),
            "Blog CSS differs from reviewed source")
    assets = git("ls-tree", "-r", "--name-only", commit, "procurement_core/assets/brand").decode().splitlines()
    for asset in assets:
        if not asset.endswith((".css", ".woff2")):
            continue
        actual = read("/assets/brand/" + Path(asset).name)
        require(hashlib.sha256(actual).digest() == hashlib.sha256(git("show", f"{commit}:{asset}")).digest(),
                f"Blog brand asset differs from reviewed source: {Path(asset).name}")
    index = read("/blog").decode()
    feed = ET.fromstring(read("/blog/feed.xml"))
    feed_urls = {item.findtext("link") for item in feed.findall("channel/item")}
    published = []
    for path in paths:
        if not path.endswith(".md"):
            continue
        metadata = json.loads(git("show", f"{commit}:{path}").decode().split("\n---\n", 1)[0][4:])
        slug = Path(path).stem
        visible = metadata["status"] == "published" and metadata["date"] <= datetime.now(timezone.utc).date().isoformat()
        post_url = ORIGIN + "/blog/" + slug
        require((post_url in feed_urls) == visible, f"Blog publication status differs from source: {slug}")
        if visible:
            require(escape(metadata["title"]) in index, f"Blog index missing post: {slug}")
            require(escape(metadata["title"]) in read("/blog/" + slug).decode(), f"Blog post unavailable: {slug}")
            published.append(slug)
    return {"blog": "passed", "published_posts": published, "css_sha256": hashlib.sha256(css).hexdigest()}


def stage(image, commit, suffix):
    commit = reviewed_commit(commit)
    require(re.fullmatch(re.escape(IMAGE) + r"@sha256:[0-9a-f]{64}", image), "Stage requires an immutable image digest")
    require(re.fullmatch(r"[a-z][a-z0-9-]{0,45}[a-z0-9]", suffix), "Invalid revision suffix")
    before = gcloud("run", "services", "describe", SERVICE)
    previous = production_revision(before)
    live = gcloud("run", "revisions", "describe", previous)
    require(runtime_identity(before["spec"]["template"]["spec"]) == runtime_identity(live["spec"]),
            "Service template differs from production credentials/config; inspect before staging")
    revision = f"{SERVICE}-{suffix}"
    gcloud("run", "deploy", SERVICE, f"--image={image}", "--no-traffic", f"--tag={suffix}",
           f"--revision-suffix={suffix}", f"--labels=source-commit={commit}")
    after = gcloud("run", "services", "describe", SERVICE)
    require(production_revision(after) == previous, "Production traffic changed during staging")
    report, details = candidate(after, revision)
    require(report["image"] == image, "Deployed image digest differs from requested image")
    require(runtime_identity(live["spec"]) == runtime_identity(details["spec"]), "Runtime credentials/config changed")
    report["previous_revision"] = previous
    report["checks"] = verify(report["url"], commit)
    report["status"] = "staged; production traffic unchanged"
    return report


def promote(revision, expected_current):
    before = gcloud("run", "services", "describe", SERVICE)
    previous = production_revision(before)
    require(previous == expected_current, "Production changed since staging; inspect and supply its current revision")
    require(revision != previous, "Revision is already serving production")
    report, details = candidate(before, revision)
    live = gcloud("run", "revisions", "describe", previous)
    require(runtime_identity(live["spec"]) == runtime_identity(details["spec"]), "Runtime credentials/config changed")
    report["previous_revision"] = previous
    report["staging_checks"] = verify(report["url"], report["commit"])
    # Recheck after the network tests so a stale run cannot overwrite a newer rollout.
    require(production_revision(gcloud("run", "services", "describe", SERVICE)) == previous,
            "Production changed while verification was running")
    try:
        gcloud("run", "services", "update-traffic", SERVICE, f"--to-revisions={revision}=100")
        require(production_revision(gcloud("run", "services", "describe", SERVICE)) == revision,
                "Production did not move to the requested revision")
        report["production_checks"] = verify(ORIGIN, report["commit"])
    except Exception:
        if production_revision(gcloud("run", "services", "describe", SERVICE)) == revision:
            gcloud("run", "services", "update-traffic", SERVICE, f"--to-revisions={previous}=100")
            print(f"Production check failed; restored {previous}", flush=True)
        raise
    report["status"] = "production; 100% traffic"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    staging = sub.add_parser("stage")
    staging.add_argument("--image", required=True)
    staging.add_argument("--commit", required=True)
    staging.add_argument("--suffix", required=True)
    promotion = sub.add_parser("promote")
    promotion.add_argument("--revision", required=True)
    promotion.add_argument("--expected-current", required=True)
    for command in (staging, promotion):
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = stage(args.image, args.commit, args.suffix) if args.action == "stage" else promote(args.revision, args.expected_current)
    report["checked_at"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("revision", "previous_revision", "commit", "image", "status")}, indent=2))


if __name__ == "__main__":
    main()
