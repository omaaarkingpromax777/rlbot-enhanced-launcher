# RLBot V5 Enhanced Launcher

Desktop app (Python + PySide6) for playing, training and ranking Rocket League bots, built on
[RLBot v5](https://github.com/RLBot/python-interface). It uses RLBot's own match runner, the
official [botpack](https://github.com/RLBot/botpack) and the RocketHost / RLLobby session
infrastructure; it does not run its own game servers.

## Sections

| Section | What it does |
|---|---|
| Play | Team size, map, one-click opponent rank (Bronze → SSL), per-slot bot choice, saved line-ups, Start/Stop Match via `rlbot.managers.MatchManager` |
| Tournaments | Single-elimination brackets (Round of 16 → quarter-final → semi-final → final) from any set of rank groups, bot count and Mechanical / Non-Mechanical filter; optional human entrant; real matches with automatic score capture, manual score entry, or clearly marked quick simulation; per-entrant W-L, win %, goals and match log; saved history. Rank Challenge: beat a chosen share of a rank group's bots to move to the next group, up to SSL |
| Bots | Pre-classified catalog (Mechanical / Non-Mechanical, rank groups), details and skill bars, botpack download/update, import of any v5 `bot.toml` folder |
| Training | Ladder from any rank to any rank; 2 wins promote, 2 losses demote; manual up/down; player rank estimate |
| Multiplayer | RLLobby session list with search and region/player filters, join by session name or IP:port with password, host on RocketHost servers (Middle East listed first) |
| Settings | Steam/Epic auto-detection, game path, RLBotServer path, botpack folder, auto-update, preferred region, language |

## Run

Requires Python 3.11+ and Windows (Rocket League + RLBot v5).

```
pip install -e .
rlbot-launcher
```

## Calibration (bot-vs-bot ranking)

```
rlbot-launcher-calibrate --bots-dir <botpack folder> --games 200 --mode 1v1
```

Runs matches chosen by active sampling (most uncertain bot vs closest-rated opponent), records
telemetry from every GamePacket (speed, supersonic time, goal-side positioning, touches, aerial
touches, air-dribble chains, recovery time, shot accuracy) and updates OpenSkill ratings. Ratings are
mapped to the 22 ranks through anchor bots (Psyonix bots and Nexto), and a rank is shown only after
40 games with low uncertainty. Results are written to `ratings.json` / `profiles.json` in the app data
folder and override the bundled estimates in the Bots section.

The bundled ranks and skill values in `data/catalog.json` are **initial estimates** from bot type and
developer descriptions, not measurements, until calibration runs.

## Known limits

- Console players (PlayStation / Xbox / Switch) cannot join RLBot matches.
- Bots cannot be added to official Psyonix Private Matches; sessions are LAN / RocketHost.
- Current RocketHost servers choose the session name themselves and start without a password; the
  launcher sends name/password for servers that support them.
- RocketHost regions depend on which servers the operator runs (only EU-HEL at the time of writing).

## Development

```
pip install -e .[dev]
pytest
```
