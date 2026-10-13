"""
Yahoo Fantasy Football Plugin for LEDMatrix
Skeleton implementation with OAuth1 example for Yahoo Fantasy Sports API.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List
from BasePlugin import BasePlugin

try:
    from requests_oauthlib import OAuth1Session
except ImportError:
    OAuth1Session = None

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
        self.consumer_key = config.get('consumer_key', '')
        self.consumer_secret = config.get('consumer_secret', '')
        self.access_token = config.get('access_token', '')
        self.access_token_secret = config.get('access_token_secret', '')
        # Backward compatibility for old refresh_token field
        self.refresh_token = config.get('refresh_token', self.access_token)
        self.leagues = config.get('leagues', [])
        self.display_mode = config.get('display_mode', 'both')
        self.update_interval = config.get('update_interval', 900)
        self.text_color = tuple(config.get('text_color', [255, 255, 0]))
        self.highlight_color = tuple(config.get('highlight_color', [0, 255, 0]))

    def on_config_change(self, new_config):
        super().on_config_change(new_config)
        self._load_config(self.config)

    def _get_oauth_session(self):
        if OAuth1Session is None or requests is None:
            self.logger.error("requests-oauthlib not installed")
            return None
        if not self.consumer_key or not self.consumer_secret or not self.access_token or not self.access_token_secret:
            self.logger.warning("Yahoo OAuth credentials incomplete")
            return None
        return OAuth1Session(
            client_key=self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_token_secret,
        )

    def _fetch_league(self, league_id: str, game_code: str = "nfl") -> Dict[str, Any]:
        session = self._get_oauth_session()
        if not session:
            return {}
        # Yahoo Fantasy Sports API v2
        url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_id}"
        params = {
            "format": "json",
            # Request standings and scoreboard in one call
            # Full query can be extended as needed
        }
        try:
            resp = session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data
        except Exception as e:
            self.logger.error(f"Yahoo API error for {league_id}: {e}")
            return {}

    def update(self) -> None:
        """
        Fetch data from Yahoo Fantasy API using OAuth1.
        """
        if not self.leagues:
            self.logger.warning("No leagues configured")
            return

        cache_key = f"{self.plugin_id}_data"
        cached = self.cache_manager.get(cache_key, max_age=self.update_interval)
        if cached:
            self.data = cached
            return

        leagues_data = []
        session = self._get_oauth_session()
        if not session:
            # Fall back to placeholder if credentials missing
            self.logger.warning("OAuth session not available, using placeholder")
        
        for league_cfg in self.leagues:
            league_id = league_cfg.get("league_id")
            name = league_cfg.get("name")
            game_code = league_cfg.get("game_code", "nfl")
            
            if session:
                api_data = self._fetch_league(league_id, game_code)
                # Parse minimal info for display
                standings = []
                matchups = []
                try:
                    league = api_data.get("fantasy_content", {}).get("league", {}).get(league_id, {})
                    # Example parsing - structure varies by API response
                    # standings = league.get("standings", {}).get("teams", [])
                    # matchups = league.get("scoreboard", {}).get("weeks", [])
                    standings = league.get("standings", {}).get("teams", [])
                except Exception:
                    pass
                leagues_data.append({
                    "league_id": league_id,
                    "name": name,
                    "standings": standings,
                    "matchups": matchups,
                    "raw": api_data
                })
            else:
                leagues_data.append({
                    "league_id": league_id,
                    "name": name,
                    "standings": [],
                    "matchups": []
                })

        self.data = {
            "last_update": time.strftime("%Y-%m-%d %H:%M"),
            "leagues": leagues_data
        }
        self.cache_manager.set(cache_key, self.data)
        self.logger.info(f"Fetched data for {len(leagues_data)} league(s)")

    def display(self, force_clear: bool = False) -> None:
        """
        Render current league data to LED matrix.
        """
        if not self.data or not self.leagues:
            self._display_no_data()
            return

        try:
            leagues = self.data.get("leagues", [])
            if not leagues:
                self._display_no_data()
                return

            # Cycle through leagues
            league = leagues[self.current_league_index % len(leagues)]
            self.current_league_index += 1

            self.display_manager.clear()

            # Header
            name = league.get("name", "League")
            self.display_manager.draw_text(
                name[:16],
                x=2,
                y=10,
                color=self.text_color
            )

            standings = league.get("standings", [])
            if self.display_mode in ("standings", "both") and standings:
                # Show top 1 team as example
                team = standings[0] if isinstance(standings[0], dict) else {}
                team_name = team.get("name", "?")
                # Truncate for matrix
                team_text = team_name[:12]
                self.display_manager.draw_text(
                    team_text,
                    x=2,
                    y=26,
                    color=self.highlight_color
                )
            elif self.display_mode in ("matchups", "both"):
                self.display_manager.draw_text(
                    "Week ?",
                    x=2,
                    y=26,
                    color=self.text_color
                )
            else:
                self.display_manager.draw_text(
                    "No data",
                    x=2,
                    y=26,
                    color=self.text_color
                )

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
        return True

    def get_info(self):
        info = super().get_info()
        info['league_count'] = len(self.leagues)
        info['display_mode'] = self.display_mode
        return info
