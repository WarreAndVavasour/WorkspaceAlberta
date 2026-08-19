import { CLIENT_VERSION } from "./branding.mjs";

/** Local StreamableHTTP adapter from this repo. No credentials required. */
export const LOCAL_MCP_URL = "http://127.0.0.1:8000/mcp";

/** Documented hosted endpoint from the repo README. Public browse; no invented keys. */
export const HOSTED_MCP_URL =
  "https://elbowsupknivesout.warreandvavasour.com/mcp";

/** Placeholder GitHub Releases surface. Update fetches, if enabled, stay on this host. */
export const RELEASES_PAGE_URL =
  "https://github.com/HarleyCoops/WorkspaceAlberta/releases";

export const RELEASES_API_URL =
  "https://api.github.com/repos/HarleyCoops/WorkspaceAlberta/releases/latest";

export const ALLOWED_UPDATE_HOSTS = Object.freeze([
  "github.com",
  "api.github.com",
]);

export const DEFAULT_UI_PORT = 8787;

export function defaultProvider() {
  return {
    kind: "openai-compatible",
    baseUrl: "",
    apiKey: "",
    model: "",
  };
}

export function defaultConfig() {
  return {
    mcpUrl: process.env.WA_BOX_MCP_URL || LOCAL_MCP_URL,
    uiPort: Number(process.env.WA_BOX_PORT || DEFAULT_UI_PORT),
    updates: {
      enabled: process.env.WA_BOX_UPDATES === "1",
      releasesPageUrl: RELEASES_PAGE_URL,
      releasesApiUrl: RELEASES_API_URL,
    },
    provider: defaultProvider(),
    clientVersion: CLIENT_VERSION,
  };
}

export function mcpPresets() {
  return [
    { id: "local", label: "Local WA server", url: LOCAL_MCP_URL },
    { id: "hosted", label: "Hosted WA endpoint", url: HOSTED_MCP_URL },
  ];
}
