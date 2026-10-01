"""Deployment gates: prevent stale promotion and restore traffic after failure."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from io import BytesIO
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cloud_run_release as release


OLD = "workspacealberta-old"
NEW = "workspacealberta-new"
SPEC = {"serviceAccountName": "runtime@example.invalid", "containers": [{"env": []}]}


def service(revision=OLD):
    return {"status": {"traffic": [{"revisionName": revision, "percent": 100}]}}


class WebsiteReleaseTest(unittest.TestCase):
    def _git(self, *args):
        if args[0] == "ls-tree":
            if args[-1] == "procurement_core/assets/brand":
                return b"procurement_core/assets/brand/fonts.css\n"
            return b"procurement_core/content/blog/approved.md\n"
        if args[-1].endswith("fonts.css"):
            return b"local corporate fonts"
        if args[-1].endswith("blog.css"):
            return b"reviewed css"
        return ("---\n" + json.dumps({"status": "published", "date": "2026-10-01", "title": "Approved & ready"}) + "\n---\n\nPost.").encode()

    def _response(self, request, **kwargs):
        path = request.full_url.removeprefix("https://candidate.invalid")
        content = {
            "/assets/blog.css": b"reviewed css",
            "/assets/brand/fonts.css": b"local corporate fonts",
            "/blog": b"Approved &amp; ready",
            "/blog/approved": b"Approved &amp; ready",
            "/blog/feed.xml": ('<rss><channel><item><link>' + release.ORIGIN + '/blog/approved</link></item></channel></rss>').encode(),
        }[path]
        response = BytesIO(content)
        response.status = 200
        return response

    def test_live_blog_matches_reviewed_source(self):
        with patch.object(release, "git", side_effect=self._git), patch.object(release, "urlopen", side_effect=self._response):
            report = release.verify_website("https://candidate.invalid", "a" * 40)
        self.assertEqual(report["published_posts"], ["approved"])

    def test_stale_css_blocks_promotion(self):
        with patch.object(release, "git", side_effect=self._git), patch.object(release, "urlopen", return_value=BytesIO(b"old css")) as request:
            request.return_value.status = 200
            with self.assertRaisesRegex(RuntimeError, "Blog CSS differs"):
                release.verify_website("https://candidate.invalid", "a" * 40)

    def test_wrong_brand_asset_blocks_promotion(self):
        def wrong_asset(request, **kwargs):
            response = self._response(request, **kwargs)
            if request.full_url.endswith("fonts.css"):
                response = BytesIO(b"wrong brand fonts")
                response.status = 200
            return response
        with patch.object(release, "git", side_effect=self._git), patch.object(release, "urlopen", side_effect=wrong_asset):
            with self.assertRaisesRegex(RuntimeError, "brand asset differs"):
                release.verify_website("https://candidate.invalid", "a" * 40)

    def test_misadvertised_draft_blocks_promotion(self):
        def draft_git(*args):
            return self._git(*args).replace(b'"status": "published"', b'"status": "draft"')
        with patch.object(release, "git", side_effect=draft_git), patch.object(release, "urlopen", side_effect=self._response):
            with self.assertRaisesRegex(RuntimeError, "publication status differs"):
                release.verify_website("https://candidate.invalid", "a" * 40)


class CloudRunReleaseTest(unittest.TestCase):
    def setUp(self):
        self.candidate = patch.object(release, "candidate", return_value=(
            {"revision": NEW, "commit": "a" * 40, "url": "https://candidate.invalid"}, {"spec": deepcopy(SPEC)}))
        self.candidate.start()
        self.addCleanup(self.candidate.stop)
        self.verify = patch.object(release, "verify", return_value={}).start()
        self.addCleanup(patch.stopall)

    def test_split_traffic_requires_manual_review(self):
        with self.assertRaisesRegex(RuntimeError, "100%"):
            release.production_revision({"status": {"traffic": [
                {"revisionName": OLD, "percent": 90}, {"revisionName": NEW, "percent": 10}]}})

    @patch.object(release, "gcloud")
    def test_stale_expected_revision_never_promotes(self, gc):
        gc.return_value = service()
        with self.assertRaisesRegex(RuntimeError, "Production changed"):
            release.promote(NEW, "workspacealberta-outdated")
        self.assertEqual(gc.call_count, 1)
        self.verify.assert_not_called()

    @patch.object(release, "gcloud")
    def test_failed_candidate_checks_never_promote(self, gc):
        gc.side_effect = [service(), {"spec": SPEC}]
        self.verify.side_effect = RuntimeError("asset mismatch")
        with self.assertRaisesRegex(RuntimeError, "asset mismatch"):
            release.promote(NEW, OLD)
        self.assertFalse(any("update-traffic" in call.args for call in gc.call_args_list))

    @patch.object(release, "gcloud")
    def test_changed_runtime_identity_never_promotes(self, gc):
        different = deepcopy(SPEC)
        different["containers"][0]["env"] = [{"name": "WA_LOGIN_PROVIDER", "value": "email"}]
        gc.side_effect = [service(), {"spec": different}]
        with self.assertRaisesRegex(RuntimeError, "config changed"):
            release.promote(NEW, OLD)
        self.verify.assert_not_called()

    @patch.object(release, "gcloud")
    def test_concurrent_release_detected_after_verification(self, gc):
        gc.side_effect = [service(), {"spec": SPEC}, service("workspacealberta-other")]
        with self.assertRaisesRegex(RuntimeError, "while verification"):
            release.promote(NEW, OLD)
        self.assertFalse(any("update-traffic" in call.args for call in gc.call_args_list))

    @patch.object(release, "gcloud")
    def test_production_check_failure_restores_previous_revision(self, gc):
        gc.side_effect = [service(), {"spec": SPEC}, service(), {}, service(NEW), service(NEW), {}]
        self.verify.side_effect = [{}, RuntimeError("production unhealthy")]
        with self.assertRaisesRegex(RuntimeError, "production unhealthy"):
            release.promote(NEW, OLD)
        updates = [call.args[-1] for call in gc.call_args_list if "update-traffic" in call.args]
        self.assertEqual(updates, [f"--to-revisions={NEW}=100", f"--to-revisions={OLD}=100"])

    @patch.object(release, "gcloud")
    def test_failure_does_not_rollback_someone_elses_release(self, gc):
        gc.side_effect = [service(), {"spec": SPEC}, service(), {}, service(NEW), service("workspacealberta-other")]
        self.verify.side_effect = [{}, RuntimeError("production unhealthy")]
        with self.assertRaisesRegex(RuntimeError, "production unhealthy"):
            release.promote(NEW, OLD)
        updates = [call.args[-1] for call in gc.call_args_list if "update-traffic" in call.args]
        self.assertEqual(updates, [f"--to-revisions={NEW}=100"])

    @patch.object(release, "gcloud")
    def test_successful_promotion_checks_both_endpoints(self, gc):
        gc.side_effect = [service(), {"spec": SPEC}, service(), {}, service(NEW)]
        result = release.promote(NEW, OLD)
        self.assertEqual(result["status"], "production; 100% traffic")
        self.assertEqual([call.args[0] for call in self.verify.call_args_list],
                         ["https://candidate.invalid", release.ORIGIN])


if __name__ == "__main__":
    unittest.main()
