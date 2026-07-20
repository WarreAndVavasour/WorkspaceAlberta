"""GraphQL client for the OPERA Cloud R&A Data APIs.

Confirmed against the R&A Data APIs postman collection: every data request
is ``POST {{HostName}}/rna/v1/graphql`` with header ``x-app-key`` and a JSON
GraphQL body. ``Authorization: Bearer <token>`` carries the OAuth token and
``x-hotelid`` scopes the query to one property (standard OPERA convention).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .auth import TokenManager
from .config import Settings

DEFAULT_TIMEOUT_SECONDS = 60

#: Canned query/response pair served by MockGraphQLClient when OPERA_MOCK=1.
MOCK_SAMPLE_QUERY = "query { hotel { code name businessDate } }"
MOCK_SAMPLE_DATA: dict[str, Any] = {
    "hotel": {
        "code": "SAND01",
        "name": "Mock Sandcastle Hotel",
        "businessDate": "2026-01-01",
    }
}


class OperaAPIError(Exception):
    """Raised when OPERA returns an HTTP or GraphQL-level error.

    Carries the HTTP ``status`` (0 for GraphQL-level errors on a 200
    response) and the server-provided ``message``.
    """

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"OPERA API error (status={status}): {message}")


class GraphQLClient:
    """Executes GraphQL queries against the OPERA R&A endpoint."""

    def __init__(self, settings: Settings, token_manager: TokenManager) -> None:
        self._settings = settings
        self._tokens = token_manager

    def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run a GraphQL query and return the ``data`` object.

        Raises OperaAPIError on HTTP errors or when the response contains a
        GraphQL ``errors`` array.
        """
        s = self._settings
        body = {"query": query, "variables": variables or {}}
        request = Request(
            url=f"{s.base_url}{s.graphql_path}",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self._tokens.token()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-app-key": s.app_key,
                "x-hotelid": s.hotel_id,
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as resp:
                payload: dict[str, Any] = json.loads(resp.read().decode())
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise OperaAPIError(exc.code, detail) from exc
        except (URLError, json.JSONDecodeError) as exc:
            raise OperaAPIError(0, str(exc)) from exc

        errors = payload.get("errors")
        if errors:
            messages = "; ".join(str(e.get("message", e)) for e in errors)
            raise OperaAPIError(0, messages)

        data = payload.get("data")
        if not isinstance(data, dict):
            raise OperaAPIError(0, "response missing 'data' object")
        return data


class MockGraphQLClient:
    """Offline stand-in for GraphQLClient; serves canned data.

    Used when OPERA_MOCK=1 so the server runs with no credentials. Any
    query returns the canned sample payload; passing MOCK_SAMPLE_QUERY
    documents the intended shape.
    """

    def __init__(self, settings: Settings | None = None, token_manager: Any = None) -> None:
        self._settings = settings

    def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return the canned sample data regardless of credentials."""
        return dict(MOCK_SAMPLE_DATA)
