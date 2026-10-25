# NBA Fantasy for iPhone

Native SwiftUI, iOS 17+. Reads one file, `app.json`, that the laptop pad publishes to GitHub Pages after every refresh (`scripts/export_season.py` → `scripts/publish_season.py`). No Yahoo, no web views, no keys in the app.

Tabs: **Today** (who starts, starts per day vs the opponent), **Matchup** (per-category leans as words), **News** (your players out, the opponent's out, and whose minutes go up when someone is out). A local notification fires once per new item that touches your roster or a pickup; iOS runs the background refresh when it chooses, so open the app for the latest.

## Build (Linux, omarchy-apple-dev / xtool)

```bash
cd ios
ulimit -n 65536
xtool dev build                                              # Debug build, compile check only
~/Projects/tools/omarchy-apple-dev/ship.sh --device GRZRJ88LA9   # Release .app (xtool/NBAFantasy.app)
xtool install xtool/NBAFantasy.app                           # sign and install on the plugged-in iPhone
```

- Bundle ID `com.chamberneezy.nbafantasy` (registered 25 Oct 2026), team GRZRJ88LA9. The App Store Connect app record is created once by hand (the API cannot create apps).
- TestFlight uses the team's App Store Connect key that Lacus keeps (Mario, 25 Oct 2026); the key file stays in the Lacus folder, never in this public repo:

```bash
ASC_KEY_ID=CS56CBA59J ASC_ISSUER_ID=30779952-7155-464c-b479-c7fff3015077 \
ASC_KEY_PATH=~/Projects/mobile/ios/Lacus/AuthKey_CS56CBA59J.p8 \
~/Projects/tools/omarchy-apple-dev/ship.sh --upload
```

- Icon: `Resources/icon-source/make_icon.py` draws `AppIcon-1024.png` (a basketball, no NBA marks).
- No iOS simulator on Linux: test on the iPhone.
- The feed URL is `Feed.url` in `Sources/NBAFantasy/Feed.swift`. The laptop must be on for the feed to update.
