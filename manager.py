"""
Yahoo Fantasy Football Plugin for LEDMatrix
Skeleton implementation with OAuth2 for Yahoo Fantasy Sports API.
"""
from __future__ import annotations

import time
import base64
from typing import Any, Dict, List
from BasePlugin import BasePlugin

try:
    import requests
except ImportError:
    requests = None

class YahooFantasyPlugin(BasePlugin):
    """
    Plugin to display Yahoo Fantasy Football league info on LED Matrix.
    """

    def __init__(self, plugin_id: str, config: Dict[str, Any], display_manager, cache_manager, plugin_manager):
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)
        self._load_config(config)
        self.data: Dict[str, Any] = {}
        self.current_league_index = 0
        self.logger.info("Yahoo Fantasy Football plugin initialized")

    def _load_config(self, config: Dict[str, Any]) -> None:
        self.client_id = config.get('client_id', '')
        self.client_secret = config.get('client_secret', '')
        self.refresh_token = config.get('refresh_token', '')
        self.access_token = config.get('access_token', '')
        self.access_token_expiry = config.get('access_token_expiry', 0)
        self.redirect_uri = config.get('redirect_uri', 'https://localhost:3000/auth/callback')
        self.leagues = config.get('leagues', [])
        self.display_mode = config.get('display_mode', 'both')
        self.update_interval = config.get('update_interval', 900)
        self.text_color = tuple(config.get('text_color', [255, 255, 0]))
        self.highlight_color = tuple(config.get('highlight_color', [0, 255, 0]))

    def on_config_change(self, new_config):
        super().on_config_change(new_config)
        self._load_config(self.config)

    def _ensure_token(self) -> bool:
        """Refresh access token if expired."""
        now = int(time.time())
        if self.access_token and self.access_token_expiry > now + 60:
            return True
        if not self.refresh_token or not self.client_id or not self.client_secret:
            self.logger.warning("OAuth2 credentials incomplete, cannot refresh token")
            return False
        if requests is None:
            self.logger.error("requests not installed")
            return False
        try:
            auth_str = f"{self.client_id}:{self.client_secret}"
            b64_auth = base64.b64encode(auth_str.encode()).decode()
            headers = {
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "redirect_uri": self.redirect_uri
            }
            resp = requests.post("https://api.login.yahoo.com/oauth2/get_token", headers=headers, data=data, timeout=15)
            resp.raise_for_status()
            token_data = resp.json()
            self.access_token = token_data.get("access_token", "")
            expires_in = token_data.get("expires_in", 3600)
            self.access_token_expiry = now + int(expires_in)
            self.config['access_token'] = self.access_token
            self.config['access_token_expiry'] = self.access_token_expiry
            self.logger.info("Yahoo access token refreshed")
            return True
        except Exception as e:
            self.logger.error(f"Token refresh failed: {e}")
            return False

    def _get_headers(self) -> Dict[str, str]:
        if not self._ensure_token():
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def _fetch_league(self, league_id: str, game_code: str = "nfl") -> Dict[str, Any]:
        headers = self._get_headers()
        if not headers:
            return {}
        url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_id}"
        params = {"format": "json"}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 401:
                if self._ensure_token():
                    headers = self._get_headers()
                    resp = requests.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data
        except Exception as e:
            self.logger.error(f"Yahoo API error for {league_id}: {e}")
            return {}

    def update(self) -> None:
        if not self.leagues:
            self.logger.warning("No leagues configured")
            return
        cache_key = f"{self.plugin_id}_data"
        cached = self.cache_manager.get(cache_key, max_age=self.update_interval)
        if cached:
            self.data = cached
            return
        leagues_data = []
        if not self._ensure_token():
            self.logger.warning("OAuth session not available, using placeholder")
        for league_cfg in self.leagues:
            league_id = league_cfg.get("league_id")
            name = league_cfg.get("name")
            game_code = league_cfg.get("game_code", "nfl")
            api_data = self._fetch_league(league_id, game_code) if self.access_token else {}
            standings = []
            try:
                fc = api_data.get("fantasy_content", {})
                league = fc.get("league", {}).get(league_id, {})
                standings = league.get("standings", {}).get("teams", [])
            except Exception:
                pass
            leagues_data.append({
                "league_id": league_id,
                "name": name,
                "standings": standings,
                "raw": api_data
            })
        self.data = {"last_update": time.strftime("%Y-%m-%d %H:%M"), "leagues": leagues_data}
        self.cache_manager.set(cache_key, self.data)
        self.logger.info(f"Fetched data for {len(leagues_data)} league(s)")

    def display(self, force_clear: bool = False) -> None:
        if not self.data or not self.leagues:
            self._display_no_data()
            return
        try:
            leagues = self.data.get("leagues", [])
            if not leagues:
                self._display_no_data()
                return
            league = leagues[self.current_league_index % len(leagues)]
            self.current_league_index += 1
            self.display_manager.clear()
            name = league.get("name", "League")
            self.display_manager.draw_text(name[:16], x=2, y=10, color=self.text_color)
            standings = league.get("standings", [])
            if self.display_mode in ("standings", "both") and standings:
                team = standings[0] if isinstance(standings[0], dict) else {}
                team_name = team.get("name", "?")
                self.display_manager.draw_text(team_name[:12], x=2, y=26, color=self.highlight_color)
            elif self.display_mode in ("matchups", "both"):
                self.display_manager.draw_text("Week ?", x=2, y=26, color=self.text_color)
            else:
                self.display_manager.draw_text("No data", x=2, y=26, color=self.text_color)
            self.display_manager.update_display()
        except Exception as e:
            self.logger.error(f"Display error: {e}", exc_info=True)
            self._display_error()

    def _display_no_data(self):
        self.display_manager.clear()
        self.display_manager.draw_text("Yahoo Fantasy", x=2, y=10, color=self.text_color)
        self.display_manager.draw_text("No leagues", x=2, y=26, color=self.text_color)
        self.display_manager.update_display()

    def _display_error(self):
        self.display_manager.clear()
        self.display_manager.draw_text("Yahoo Error", x=2, y=18, color=(255, 0, 0))
        self.display_manager.update_display()

    def validate_config(self) -> bool:
        if not super().validate_config():
            return False
        if self.leagues:
            for l in self.leagues:
                if not l.get("league_id") or not l.get("name"):
                    self.logger.error("Each league requires league_id and name")
                    return False
        if not self.client_id or not self.client_secret or not self.refresh_token:
            self.logger.warning("OAuth2 credentials incomplete, plugin will not fetch live data")
        return True

    def get_info(self):
        info = super().get_info()
        info['league_count'] = len(self.leagues)
        info['display_mode'] = self.display_mode
        return info
