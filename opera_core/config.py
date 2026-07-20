"""Settings for the OPERA Cloud R&A data tap.

Endpoint facts (from research/hospitality-api-docs):

- GraphQL: ``POST {{HostName}}/rna/v1/graphql``
  (postman-collections/reporting-and-analytics/R&A Data APIs.postman_collection.json)
- Token: ``POST {{HostName}}/oauth/v1/tokens``
  (rest-api-specs/property/v1/oauth.json, operationId ``getToken``)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_GRAPHQL_PATH = "/rna/v1/graphql"
DEFAULT_TOKEN_PATH = "/oauth/v1/tokens"
DEFAULT_GRANT_TYPE = "password"

_TRUTHY = {"1", "true", "yes", "on"}


@dataclass
class Settings:
    """Connection settings for one OPERA Cloud environment."""

    base_url: str = ""
    graphql_path: str = DEFAULT_GRAPHQL_PATH
    token_path: str = DEFAULT_TOKEN_PATH
    app_key: str = ""
    client_id: str = ""
    client_secret: str = ""
    hotel_id: str = ""
    username: str = ""
    password: str = ""
    grant_type: str = DEFAULT_GRANT_TYPE
    mock: bool = False
    data_dir: Path = field(default_factory=lambda: REPO_ROOT / "data" / "opera")

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from OPERA_* environment variables."""
        return cls(
            base_url=os.environ.get("OPERA_BASE_URL", "").rstrip("/"),
            graphql_path=os.environ.get("OPERA_GRAPHQL_PATH", DEFAULT_GRAPHQL_PATH),
            token_path=os.environ.get("OPERA_TOKEN_PATH", DEFAULT_TOKEN_PATH),
            app_key=os.environ.get("OPERA_APP_KEY", ""),
            client_id=os.environ.get("OPERA_CLIENT_ID", ""),
            client_secret=os.environ.get("OPERA_CLIENT_SECRET", ""),
            hotel_id=os.environ.get("OPERA_HOTEL_ID", ""),
            username=os.environ.get("OPERA_USERNAME", ""),
            password=os.environ.get("OPERA_PASSWORD", ""),
            grant_type=os.environ.get("OPERA_GRANT_TYPE", DEFAULT_GRANT_TYPE),
            mock=os.environ.get("OPERA_MOCK", "").strip().lower() in _TRUTHY,
            data_dir=Path(os.environ["OPERA_DATA_DIR"])
            if os.environ.get("OPERA_DATA_DIR")
            else REPO_ROOT / "data" / "opera",
        )
