"""Pure-logic Spotify tests only — nothing here touches the Spotify API."""
from urllib.parse import parse_qs, urlparse

from app.modules.spotify.service import SpotifyService


def test_get_auth_url_contains_oauth_params():
    url = SpotifyService().get_auth_url(telegram_user_id=42)
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "accounts.spotify.com"

    params = parse_qs(parsed.query)
    assert params["response_type"] == ["code"]
    assert params["state"] == ["42"]
    assert "user-library-read" in params["scope"][0]
