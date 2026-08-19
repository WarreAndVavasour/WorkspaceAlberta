import {
  ALLOWED_UPDATE_HOSTS,
  RELEASES_API_URL,
  RELEASES_PAGE_URL,
  defaultConfig,
} from "./config.mjs";

function hostOf(url) {
  return new URL(url).hostname;
}

export function allowedUpdateHosts() {
  return [...ALLOWED_UPDATE_HOSTS];
}

export function assertAllowedUpdateUrl(url) {
  const host = hostOf(url);
  if (!ALLOWED_UPDATE_HOSTS.includes(host)) {
    throw new Error(`Update URL host is not allowed: ${host}`);
  }
  return url;
}

export async function checkForUpdates(config = defaultConfig(), fetchImpl = fetch) {
  const updates = config.updates || {};
  if (!updates.enabled) {
    return {
      enabled: false,
      status: "disabled",
      releasesPageUrl: RELEASES_PAGE_URL,
    };
  }

  const apiUrl = assertAllowedUpdateUrl(updates.releasesApiUrl || RELEASES_API_URL);
  const response = await fetchImpl(apiUrl, {
    headers: {
      Accept: "application/vnd.github+json",
      "User-Agent": "workspacealberta-box",
    },
  });
  if (!response.ok) {
    throw new Error(`GitHub Releases check failed (${response.status})`);
  }
  const body = await response.json();
  return {
    enabled: true,
    status: "ok",
    tag: body.tag_name || "",
    htmlUrl: body.html_url || RELEASES_PAGE_URL,
    releasesPageUrl: RELEASES_PAGE_URL,
  };
}
