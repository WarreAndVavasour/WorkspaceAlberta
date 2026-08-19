import assert from "node:assert/strict";
import test from "node:test";

import { APP_NAME } from "../src/branding.mjs";
import { startUiServer } from "../src/ui-server.mjs";

test("UI server boots and serves WorkspaceAlberta Box chrome", async () => {
  const { server, url } = await startUiServer({ port: 0 });
  try {
    const page = await fetch(url);
    assert.equal(page.status, 200);
    const html = await page.text();
    assert.match(html, /<title>WorkspaceAlberta Box<\/title>/);
    assert.match(html, /A product of Warre &amp; Vavasour/);
    assert.equal(html.toLowerCase().includes(("Deep" + "Seek").toLowerCase()), false);

    const about = await (await fetch(new URL("/api/about", url))).json();
    assert.equal(about.name, APP_NAME);
    assert.equal(about.vendor, "Warre & Vavasour");

    const updates = await (await fetch(new URL("/api/updates", url))).json();
    assert.equal(updates.enabled, false);
    assert.match(updates.releasesPageUrl, /github\.com\/HarleyCoops\/WorkspaceAlberta\/releases/);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
