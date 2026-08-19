import assert from "node:assert/strict";
import test from "node:test";

import { ALLOWED_UPDATE_HOSTS, RELEASES_API_URL, RELEASES_PAGE_URL, defaultConfig } from "../src/config.mjs";
import { allowedUpdateHosts, assertAllowedUpdateUrl, checkForUpdates } from "../src/update-check.mjs";

test("update checks default to off and only name GitHub Releases", () => {
  const config = defaultConfig();
  assert.equal(config.updates.enabled, false);
  assert.equal(config.updates.releasesPageUrl, RELEASES_PAGE_URL);
  assert.match(RELEASES_PAGE_URL, /^https:\/\/github\.com\/HarleyCoops\/WorkspaceAlberta\/releases$/);
  assert.match(RELEASES_API_URL, /^https:\/\/api\.github\.com\/repos\/HarleyCoops\/WorkspaceAlberta\/releases\/latest$/);
});

test("allowed update hosts are GitHub only", () => {
  const hosts = allowedUpdateHosts();
  assert.deepEqual(hosts, ["github.com", "api.github.com"]);
  assert.equal(ALLOWED_UPDATE_HOSTS.some((host) => host.endsWith(".cn")), false);
  assert.equal(
    hosts.some((host) => host.includes("deep" + "seek")),
    false,
  );
});

test("assertAllowedUpdateUrl rejects non-GitHub hosts", () => {
  assert.equal(assertAllowedUpdateUrl(RELEASES_API_URL), RELEASES_API_URL);
  assert.throws(() => assertAllowedUpdateUrl("https://example.com/releases"), /not allowed/);
});

test("checkForUpdates is a no-op when disabled", async () => {
  const result = await checkForUpdates(defaultConfig(), () => {
    throw new Error("fetch must not run when updates are disabled");
  });
  assert.equal(result.enabled, false);
  assert.equal(result.status, "disabled");
});
