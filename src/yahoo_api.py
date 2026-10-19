"""Yahoo Fantasy Sports API, read-only, for the season pad.

Credentials live only on this laptop: ``.env.yahoo`` (client id and secret,
typed in by Mario) and ``data/yahoo_token.json`` (the OAuth token from the
one-time sign-in). Both are git-ignored and readable by the owner only.

The pad never writes to Yahoo. Adds, drops and lineups stay Mario's clicks.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.yahoo"
TOKEN_PATH = ROOT / "data" / "yahoo_token.json"
AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
API_BASE = "https://fantasysports.yahooapis.com/fantasy/v2/"
REDIRECT_URI = "https://localhost:8080"
LEAGUE_ID = "51867"
# Fantasy Sports, read only.
SCOPE = "fspt-r"
# Refresh this long before the hour-long token runs out.
EXPIRY_MARGIN = 120


class YahooNotConnected(RuntimeError):
    """No client keys or no token yet: run scripts/yahoo_auth.py."""


def credentials(path: Path = ENV_PATH) -> tuple[str, str]:
    if not path.exists():
        raise YahooNotConnected(f"No {path.name}. Save YAHOO_CLIENT_ID and YAHOO_CLIENT_SECRET there first.")
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key.strip()] = value.strip().strip("'\"")
    try:
        return values["YAHOO_CLIENT_ID"], values["YAHOO_CLIENT_SECRET"]
    except KeyError as exc:
        raise YahooNotConnected(f"{path.name} is missing {exc.args[0]}.") from None


def authorize_url() -> str:
    client_id, _ = credentials()
    # Without an explicit fspt-r scope Yahoo issues a token the Fantasy API refuses (403).
    query = {"client_id": client_id, "redirect_uri": REDIRECT_URI, "response_type": "code", "scope": SCOPE, "language": "en-us"}
    return f"{AUTH_URL}?{urlencode(query)}"


def code_from(text: str) -> str:
    """The sign-in code, from the bare code or the whole localhost address Yahoo sent the browser to."""
    text = text.strip()
    if "code=" in text:
        return parse_qs(urlparse(text).query).get("code", [""])[0] or text.split("code=", 1)[1].split("&", 1)[0]
    return text


def _save_token(payload: dict, path: Path = TOKEN_PATH) -> dict:
    token = dict(payload)
    token["expires_at"] = time.time() + float(token.get("expires_in", 3600))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(token, indent=2), encoding="utf-8")
    os.chmod(path, 0o600)
    return token


def _token_request(data: dict) -> dict:
    import requests

    client_id, secret = credentials()
    response = requests.post(TOKEN_URL, data=data, auth=(client_id, secret), timeout=30)
    if response.status_code != 200:
        raise YahooNotConnected(f"Yahoo refused the sign-in ({response.status_code}): {response.text[:200]}")
    return response.json()


def exchange_code(code: str) -> dict:
    """Trade the one-time sign-in code for a token, and keep it."""
    return _save_token(_token_request({"grant_type": "authorization_code", "redirect_uri": REDIRECT_URI, "code": code_from(code)}))


def access_token(path: Path = TOKEN_PATH) -> str:
    if not path.exists():
        raise YahooNotConnected("Not signed in to Yahoo yet. Run scripts/yahoo_auth.py.")
    token = json.loads(path.read_text(encoding="utf-8"))
    if time.time() > float(token.get("expires_at", 0)) - EXPIRY_MARGIN:
        refreshed = _token_request({"grant_type": "refresh_token", "redirect_uri": REDIRECT_URI, "refresh_token": token["refresh_token"]})
        refreshed.setdefault("refresh_token", token["refresh_token"])
        token = _save_token(refreshed, path)
    return token["access_token"]


def get(resource: str, timeout: int = 30) -> dict:
    """GET one Fantasy API resource as JSON, e.g. ``users;use_login=1/games;game_keys=nba``."""
    import requests

    url = API_BASE + resource.lstrip("/")
    response = requests.get(
        url,
        params={"format": "json"},
        headers={"Authorization": f"Bearer {access_token()}"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()
