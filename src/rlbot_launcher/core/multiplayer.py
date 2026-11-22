"""Multiplayer sessions built on the existing RLBot v5 infrastructure (RocketHost + RLLobby).

The launcher never creates new game servers: hosting uses RocketHost's dedicated
servers (bots run server-side) and joining uses RLLobby listings or a direct IP:port.
Both end with the same Rocket League console command the official v5 GUI sends.
"""

from dataclasses import dataclass, field
from urllib.parse import urlencode

import requests

RHOST_SERVER_LIST = "http://serverlist.jetfox.ovh/servers"
RLLOBBY_URL = "https://rllobby.martinn.no/rllobby/lobby"

REGIONS = {
    "ME": "Middle East",
    "EU": "Europe",
    "USE": "US East",
    "USW": "US West",
    "SAM": "South America",
    "ASIA": "Asia",
    "OCE": "Oceania",
    "SAF": "Africa",
}
REGION_PREFIXES = {
    "ME": ("ME", "UAE", "DXB", "BAH", "KSA", "RUH", "JED", "DOH", "KWI", "TLV"),
    "EU": ("EU",),
    "USE": ("USE", "US-E", "NA-E"),
    "USW": ("USW", "US-W", "NA-W"),
    "SAM": ("SAM", "SA-", "BR"),
    "ASIA": ("ASIA", "AS-", "SG", "JP", "IN-"),
    "OCE": ("OCE", "AU", "NZ"),
    "SAF": ("SAF", "AF-", "ZA"),
}


def region_of(location: str) -> str:
    loc = (location or "").upper()
    for code, prefixes in REGION_PREFIXES.items():
        if any(loc.startswith(p) for p in prefixes):
            return code
    return "EU" if loc.startswith("EU") else "?"


@dataclass
class RHostServer:
    ip: str
    port: str
    location: str
    domain: str = ""

    @property
    def address(self) -> str:
        return f"{self.domain or self.ip}:{self.port}"

    @property
    def region(self) -> str:
        return region_of(self.location)


@dataclass
class Lobby:
    id: str
    name: str
    map: str
    player_count: int
    has_password: bool
    ip: str
    port: int
    players: list[str] = field(default_factory=list)
    description: str = ""
    seconds_since_update: int = 0

    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"

    @property
    def region(self) -> str:
        return region_of(self.name)


def sort_by_region_priority(items: list, preferred: str = "ME") -> list:
    order = [preferred] + [r for r in REGIONS if r != preferred]
    rank = {r: i for i, r in enumerate(order)}
    return sorted(items, key=lambda x: (rank.get(x.region, len(order)), getattr(x, "name", getattr(x, "location", ""))))


def fetch_servers(session: requests.Session | None = None) -> list[RHostServer]:
    r = (session or requests).get(RHOST_SERVER_LIST, timeout=10)
    r.raise_for_status()
    return [RHostServer(s["ip"], str(s["port"]), s.get("location", ""), s.get("domain", "")) for s in r.json()]


def fetch_server_bots(server: RHostServer, session: requests.Session | None = None) -> list[dict]:
    r = (session or requests).get(f"http://{server.address}/status", timeout=10)
    r.raise_for_status()
    return [b for b in r.json().get("bots", {}).get("list", []) if b.get("status") == "ready"]


def fetch_lobbies(session: requests.Session | None = None) -> list[Lobby]:
    r = (session or requests).get(RLLOBBY_URL, timeout=10)
    r.raise_for_status()
    return [
        Lobby(
            id=str(d.get("id", "")), name=d.get("name", ""), map=d.get("map", ""),
            player_count=int(d.get("playerCount", 0)), has_password=bool(d.get("hasPassword")),
            ip=d.get("ipAddress", ""), port=int(d.get("port", 0)), players=d.get("players") or [],
            description=d.get("description", ""), seconds_since_update=int(d.get("secondsSinceUpdate", 0)),
        )
        for d in _lobby_list(r.json())
    ]


def _lobby_list(data) -> list[dict]:
    return (data.get("lobbies") or []) if isinstance(data, dict) else data


def find_lobby(lobbies: list[Lobby], name: str) -> Lobby | None:
    n = name.strip().lower()
    exact = [lb for lb in lobbies if lb.name.lower() == n]
    if exact:
        return exact[0]
    partial = [lb for lb in lobbies if n and n in lb.name.lower()]
    return partial[0] if len(partial) == 1 else None


def join_command(address: str, password: str = "") -> str:
    return f"open {address}?Lan?Password={password}"


def host_start_command(server_message: str, password: str = "") -> str:
    return f"start {server_message}/?Lan?Password={password}"


@dataclass
class HostRequest:
    server: RHostServer
    map_upk: str
    blue_bots: list[str]
    orange_bots: list[str]
    game_mode: str = "soccar"
    mutators: str = ""
    session_name: str = ""
    password: str = ""

    def url(self) -> str:
        params = {
            "mapName": self.map_upk,
            "gameMode": self.game_mode,
            "mutators": self.mutators,
            "networkOptions": "?Lan?Listen",
            "rlbot": "yes",
            "blueBots": ",".join(self.blue_bots),
            "orangeBots": ",".join(self.orange_bots),
        }
        # Name/password are forwarded for servers that support them; current RocketHost
        # servers assign the lobby name themselves and ignore these parameters.
        if self.session_name:
            params["lobbyName"] = self.session_name
        if self.password:
            params["password"] = self.password
        return f"http://{self.server.address}/?{urlencode(params)}"


def request_host(req: HostRequest, session: requests.Session | None = None) -> str:
    """Ask RocketHost to start a match; returns the address message to pass to `start`."""
    r = (session or requests).get(req.url(), timeout=120)
    r.raise_for_status()
    data = r.json()
    if not data.get("success", data.get("Success")):
        raise RuntimeError(data.get("message") or data.get("Message") or "RocketHost refused the match")
    return data.get("message") or data.get("Message")
