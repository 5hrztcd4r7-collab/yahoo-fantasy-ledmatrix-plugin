# Yahoo Fantasy Football Plugin for LEDMatrix

Display your Yahoo Fantasy Football leagues on a Raspberry Pi RGB LED Matrix running ChuckBuilds LEDMatrix.

## Features
* Support for multiple leagues
* Configurable display mode: standings, matchups, or both
* Rotates through leagues automatically
* Caching to respect Yahoo API rate limits

## Setup

1. Get Yahoo Developer App credentials
   * Create an app at https://developer.apps.yahoo.com
   * Request Fantasy Sports scope
   * Obtain Consumer Key/Secret and generate a refresh token

2. Find your league IDs
   * League URL looks like `https://football.fantasy.yahoo.com/f1/12345/l/67890`
   * League ID is `12345.l.67890`

3. Install plugin
   * Copy this folder to your LEDMatrix plugin repo, or install via GitHub URL in the web UI
   * Open http://your-pi-ip:5000 → Plugin Manager → Configure
   * Add your leagues in the config UI

## Configuration
* `consumer_key`, `consumer_secret`, `refresh_token` - Yahoo OAuth
* `leagues` - Array of `{league_id, name, game_code}`
* `display_mode` - standings / matchups / both
* `update_interval` - seconds between API refreshes
* `display_duration` - seconds per league on screen

## Implementation Notes
This skeleton includes the manifest, config schema and BasePlugin structure. You still need to implement:
* OAuth token refresh using `requests-oauthlib`
* Calls to `https://fantasysports.yahooapis.com/fantasy/v2/league/{league_id}`
* Parsing standings and matchups
* Rendering text with scrolling for long names

The plugin will currently show placeholder "No data yet" until the API code is added.

## License
GPL-3.0-or-later
