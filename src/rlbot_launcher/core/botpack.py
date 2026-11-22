"""Download, update and scan the official RLBot v5 botpack (github.com/RLBot/botpack)."""

import platform
import tarfile
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests

GITHUB_API = "https://api.github.com"


@dataclass
class Release:
    tag: str
    asset_url: str
    size: int


def asset_name() -> str:
    return "botpack_x86_64-windows.tar.xz" if platform.system() == "Windows" else "botpack_x86_64-linux.tar.xz"


def latest_release(repo: str = "RLBot/botpack", session: requests.Session | None = None) -> Release:
    s = session or requests
    r = s.get(f"{GITHUB_API}/repos/{repo}/releases/latest", timeout=20)
    r.raise_for_status()
    data = r.json()
    want = asset_name()
    for a in data.get("assets", []):
        if a["name"] == want:
            return Release(data["tag_name"], a["browser_download_url"], a.get("size", 0))
    raise RuntimeError(f"{want} not found in {repo} {data.get('tag_name')}")


def needs_update(current_tag: str, repo: str = "RLBot/botpack") -> tuple[bool, Release]:
    rel = latest_release(repo)
    return rel.tag != current_tag, rel


def download_and_extract(rel: Release, dest: Path, progress: Callable[[int, int], None] | None = None) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest.parent / f"{dest.name}.download.tar.xz"
    with requests.get(rel.asset_url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", rel.size or 0))
        done = 0
        with open(archive, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    with tarfile.open(archive, "r:xz") as tar:
        tar.extractall(dest, filter="data")
    archive.unlink(missing_ok=True)


def scan_bots(root: Path) -> dict[str, Path]:
    """Return bot display name -> bot.toml for every RLBot v5 bot config under root."""
    found: dict[str, Path] = {}
    if not root.exists():
        return found
    for p in root.rglob("*.toml"):
        if not (p.name == "bot.toml" or p.name.endswith(".bot.toml")):
            continue
        try:
            data = tomllib.loads(p.read_text("utf-8", errors="ignore"))
        except tomllib.TOMLDecodeError:
            continue
        name = data.get("settings", {}).get("name")
        if name and name not in ("ATBA", "ExampleBotCPP"):
            found.setdefault(name, p)
    return found
