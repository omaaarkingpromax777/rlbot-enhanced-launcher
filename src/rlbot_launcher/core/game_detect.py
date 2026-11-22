"""Find a Rocket League installation (Steam or Epic) and whether the game is running."""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import psutil

RL_STEAM_APPID = "252950"
RL_EXE = "RocketLeague.exe"


@dataclass
class GameInstall:
    launcher: str  # Steam | Epic
    path: Path


def _steam_roots() -> list[Path]:
    roots = []
    for env in ("ProgramFiles(x86)", "ProgramFiles"):
        if v := os.environ.get(env):
            roots.append(Path(v) / "Steam")
    roots += [Path.home() / ".steam" / "steam", Path.home() / ".local" / "share" / "Steam"]
    return [r for r in roots if r.exists()]


def parse_library_folders(vdf_text: str) -> list[Path]:
    return [Path(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"([^"]+)"', vdf_text)]


def find_steam(roots: list[Path] | None = None) -> GameInstall | None:
    for root in roots if roots is not None else _steam_roots():
        libs = [root]
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            libs += parse_library_folders(vdf.read_text("utf-8", errors="ignore"))
        for lib in libs:
            if (lib / "steamapps" / f"appmanifest_{RL_STEAM_APPID}.acf").exists():
                return GameInstall("Steam", lib / "steamapps" / "common" / "rocketleague")
    return None


def find_epic(manifest_dir: Path | None = None) -> GameInstall | None:
    base = manifest_dir or Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    if not base.exists():
        return None
    for item in base.glob("*.item"):
        try:
            data = json.loads(item.read_text("utf-8", errors="ignore"))
        except json.JSONDecodeError:
            continue
        if data.get("DisplayName", "").lower().startswith("rocket league") or data.get("AppName") == "Sugar":
            return GameInstall("Epic", Path(data.get("InstallLocation", "")))
    return None


def detect() -> GameInstall | None:
    return find_steam() or find_epic()


def is_running() -> bool:
    for p in psutil.process_iter(["name"]):
        if (p.info.get("name") or "").lower() == RL_EXE.lower():
            return True
    return False
