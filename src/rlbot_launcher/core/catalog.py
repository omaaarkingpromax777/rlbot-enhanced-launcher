"""Bundled, pre-classified bot catalog merged with locally installed bots."""

import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from .ranks import RankBand, group_of, parse_band

SKILL_KEYS = ("defense", "offense", "positioning", "air_dribble", "flick", "recovery", "rotation")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "bot"


@dataclass
class BotEntry:
    name: str
    bot_type: str
    source: str
    language: str = ""
    developer: str = ""
    modes: str = ""
    category: str = "—"
    style: str = "—"
    expected_level: str = "—"
    skills: dict[str, int] = field(default_factory=dict)
    in_rank_system: bool = True
    confidence: str = ""
    description: str = ""
    rating: float | None = None
    rating_games: int = 0
    toml_path: Path | None = None

    @property
    def slug(self) -> str:
        return slugify(self.name)

    @property
    def band(self) -> RankBand | None:
        return parse_band(self.expected_level)

    @property
    def rank_group(self) -> str:
        b = self.band
        return group_of(b.mid) if b else "—"

    @property
    def is_mechanical(self) -> bool:
        return self.category == "Mechanical"

    @property
    def installed(self) -> bool:
        return self.toml_path is not None or self.bot_type.startswith("Psyonix")

    @property
    def overall(self) -> float:
        if not self.skills:
            return 0.0
        return round(sum(self.skills.values()) / len(self.skills), 1)


def load_bundled() -> list[BotEntry]:
    raw = json.loads(resources.files("rlbot_launcher.data").joinpath("catalog.json").read_text("utf-8"))
    return [from_dict(d) for d in raw]


def from_dict(d: dict) -> BotEntry:
    return BotEntry(
        name=d["name"],
        bot_type=d.get("type", ""),
        source=d.get("source", ""),
        language=d.get("language", ""),
        developer=d.get("developer", ""),
        modes=d.get("modes", ""),
        category=d.get("category", "—"),
        style=d.get("style", "—"),
        expected_level=d.get("expected_level", "—"),
        skills={k: int(d[k]) for k in SKILL_KEYS if k in d},
        in_rank_system=bool(d.get("in_rank_system", True)),
        confidence=d.get("confidence", ""),
        description=d.get("description", ""),
    )


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


class Catalog:
    def __init__(self, entries: list[BotEntry]):
        self.entries = entries

    @classmethod
    def bundled(cls) -> "Catalog":
        return cls(load_bundled())

    def rankable(self) -> list[BotEntry]:
        return [e for e in self.entries if e.in_rank_system]

    def find(self, name: str) -> BotEntry | None:
        n = _norm(name)
        for e in self.entries:
            if _norm(e.name) == n:
                return e
        return None

    def attach_installed(self, installed: dict[str, Path]) -> None:
        """installed: bot display name -> bot.toml path. Unknown bots are added as unclassified."""
        for name, path in installed.items():
            e = self.find(name)
            if e is None:
                e = BotEntry(name=name, bot_type="غير مصنف", source="Local", expected_level="—",
                             in_rank_system=False, confidence="غير مقاس")
                self.entries.append(e)
            e.toml_path = path

    def apply_ratings(self, ratings: dict[str, dict]) -> None:
        """ratings: slug -> {'rating': float, 'games': int, 'rank': str}. Measured values win over priors."""
        for e in self.entries:
            r = ratings.get(e.slug)
            if not r:
                continue
            e.rating = r.get("rating")
            e.rating_games = r.get("games", 0)
            if r.get("rank"):
                e.expected_level = r["rank"]
                e.confidence = "مقاس"

    def filter(self, *, text: str = "", category: str | None = None, group: str | None = None,
               installed_only: bool = False, include_unranked: bool = False) -> list[BotEntry]:
        out = []
        t = text.lower().strip()
        for e in self.entries:
            if not include_unranked and not e.in_rank_system:
                continue
            if category and e.category != category:
                continue
            if group and e.rank_group != group:
                continue
            if installed_only and not e.installed:
                continue
            if t and t not in f"{e.name} {e.developer} {e.style} {e.source}".lower():
                continue
            out.append(e)
        return out

    def for_rank(self, idx: int, category: str | None = None, installed_only: bool = False) -> list[BotEntry]:
        out = []
        for e in self.rankable():
            b = e.band
            if not re.search(r"[A-Za-z0-9]", e.name):
                continue
            if b and b.contains(idx) and (not category or e.category == category):
                if installed_only and not e.installed:
                    continue
                out.append(e)
        # Narrowest band first: it is the most specific match for the rank.
        out.sort(key=lambda e: (e.band.high - e.band.low, e.name))
        return out
