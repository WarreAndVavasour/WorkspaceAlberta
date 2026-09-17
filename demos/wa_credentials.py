"""Central workspace identity + OAuth-style credential store for
WorkspaceAlberta clients.

Store location (fleet convention): ~/.config/workspacealberta/credentials
Written 0600. Shape:

    {
      "wa_live": "wa_live_...",              # optional subscriber key
      "business_profile": { ... },           # the ONE business identity
      "platforms": {                          # per-platform OAuth slots
        "canadabuys": {"token": "", "expires": 0},
        "apc":        {"token": "", "expires": 0}
      }
    }

Every client (ZCode, Grok Bot, harness, mobile) reads this same file, so the
business identity and platform tokens stay central. `ensure()` seeds the file
on first use and returns the loaded store.
"""
import json
import os
import stat
from pathlib import Path

STORE = Path.home() / ".config" / "workspacealberta" / "credentials"

DEFAULT_PROFILE = {
    "company_name": "Rocky Mountain Carpentry",
    "location": "Rocky Mountain House, Alberta",
    "description": (
        "Carpentry contractor serving Clearwater County and Nordegg: framing, "
        "finishing, custom woodwork, renovations, design/build small commercial "
        "and residential projects."
    ),
    "capabilities": ["carpentry", "framing", "finishing", "renovation",
                     "custom woodwork", "design/build", "residential",
                     "construction"],
    "industries": ["construction", "lumber"],
}

PLATFORMS = ["canadabuys", "apc"]


def load() -> dict:
    if STORE.exists():
        return json.loads(STORE.read_text())
    return {}


def ensure(profile: dict | None = None) -> dict:
    """Load the store, seeding it on first run. Returns the store dict."""
    store = load()
    changed = False
    if "business_profile" not in store:
        store["business_profile"] = profile or DEFAULT_PROFILE
        changed = True
    if "wa_live" not in store:
        store["wa_live"] = ""
        changed = True
    store.setdefault("platforms", {})
    for name in PLATFORMS:
        if name not in store["platforms"]:
            store["platforms"][name] = {"token": "", "expires": 0}
            changed = True
    if changed:
        save(store)
    return store


def save(store: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(store, indent=2))
    STORE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600


def auth_headers(store: dict) -> dict:
    """Auth headers the MCP client should send, if a subscriber key exists."""
    key = store.get("wa_live", "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


def platform_token(store: dict, platform: str) -> str:
    return store.get("platforms", {}).get(platform, {}).get("token", "")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="workspacealberta credential store")
    ap.add_argument("--set-key", help="store a wa_live_ subscriber key")
    ap.add_argument("--set-platform", nargs=2, metavar=("NAME", "TOKEN"),
                    help="store a platform OAuth token (canadabuys|apc)")
    ap.add_argument("--show", action="store_true", help="print store with secrets masked")
    args = ap.parse_args()
    store = ensure()
    if args.set_key:
        store["wa_live"] = args.set_key
        save(store)
    if args.set_platform:
        name, tok = args.set_platform
        store["platforms"][name] = {"token": tok, "expires": 0}
        save(store)
    if args.show or not (args.set_key or args.set_platform):
        masked = json.loads(json.dumps(store))
        if masked.get("wa_live"):
            masked["wa_live"] = masked["wa_live"][:8] + "…"
        for p in masked.get("platforms", {}).values():
            if p.get("token"):
                p["token"] = p["token"][:8] + "…"
        print(json.dumps(masked, indent=2))
