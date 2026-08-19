import assert from "node:assert/strict";
import test from "node:test";

import {
  ABOUT_BODY,
  ABOUT_TITLE,
  APP_NAME,
  APP_SHORT_NAME,
  TRAY_TOOLTIP,
  VENDOR,
  WINDOW_TITLE,
} from "../src/branding.mjs";
import { defaultProvider } from "../src/config.mjs";

const CHROME = [
  APP_NAME,
  APP_SHORT_NAME,
  WINDOW_TITLE,
  TRAY_TOOLTIP,
  ABOUT_TITLE,
  ABOUT_BODY,
  VENDOR,
];

test("product chrome is WorkspaceAlberta Box / Warre & Vavasour", () => {
  assert.equal(APP_NAME, "WorkspaceAlberta Box");
  assert.equal(WINDOW_TITLE, "WorkspaceAlberta Box");
  assert.equal(TRAY_TOOLTIP, "WorkspaceAlberta Box");
  assert.equal(VENDOR, "Warre & Vavasour");
  assert.match(ABOUT_BODY, /Warre & Vavasour/);
  assert.match(ABOUT_BODY, /DSH and other tools get added later/);
});

test("chrome strings do not use a third-party wordmark", () => {
  const banned = "Deep" + "Seek";
  for (const value of CHROME) {
    assert.equal(value.toLowerCase().includes(banned.toLowerCase()), false, value);
  }
});

test("provider slot starts empty", () => {
  const provider = defaultProvider();
  assert.equal(provider.baseUrl, "");
  assert.equal(provider.apiKey, "");
  assert.equal(provider.model, "");
});
