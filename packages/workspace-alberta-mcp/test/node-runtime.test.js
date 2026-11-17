import assert from "node:assert/strict";
import test from "node:test";
import { supportsNodeVersion } from "../bin/node-runtime.js";

test("rejects vulnerable releases, unsupported majors and prereleases", () => {
  for (const version of ["18.20.8", "20.20.0", "22.23.3", "24.22.0", "25.9.0", "26.0.0", "26.12.0", "27.0.0", "24.22.1-rc.1", "invalid"]) {
    assert.equal(supportsNodeVersion(version), false, version);
  }
});
test("accepts patched supported floors and subsequent releases", () => {
  for (const version of ["22.23.4", "22.24.0", "24.22.1", "24.22.2", "24.23.0", "26.12.1", "26.13.0"]) {
    assert.equal(supportsNodeVersion(version), true, version);
  }
});
