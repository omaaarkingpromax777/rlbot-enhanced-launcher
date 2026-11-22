"""Single-elimination tournaments between bots (and optionally the local player)."""

import json
import math
import random
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .catalog import BotEntry, Catalog
from .match import MatchSpec, Slot, psyonix_for_rank
from .ranks import GROUPS, RANKS, group_of, rank_index, rank_to_rating

HUMAN_ID = "human"


@dataclass
class Participant:
    id: str
    name: str
    kind: str  # bot | psyonix | human
    rank: str
    rank_idx: int
    category: str = "—"
    bot_type: str = ""
    toml_path: str | None = None
    psyonix_skill: str = "AllStar"
    seed: int = 0

    def slot(self, team: int) -> Slot:
        if self.kind == "human":
            return Slot("human", team)
        if self.kind == "psyonix":
            return Slot("psyonix", team, self.name, psyonix_skill=self.psyonix_skill)
        return Slot("bot", team, self.name, toml_path=Path(self.toml_path) if self.toml_path else None)


@dataclass
class BracketMatch:
    id: str
    round: int
    index: int
    a: str | None = None
    b: str | None = None
    score_a: int | None = None
    score_b: int | None = None
    winner: str | None = None
    simulated: bool = False
    played_at: str | None = None

    @property
    def ready(self) -> bool:
        return self.a is not None and self.b is not None and self.winner is None

    @property
    def is_bye(self) -> bool:
        return self.winner is not None and self.score_a is None


def round_name(round_idx: int, total_rounds: int) -> str:
    left = total_rounds - round_idx
    return {1: "النهائي", 2: "نصف النهائي", 3: "ربع النهائي"}.get(left, f"دور الـ {2 ** left}")


@dataclass
class Tournament:
    id: str
    name: str
    created: str
    groups: list[str]
    category: str  # "" = all
    team_size: int
    map_name: str
    participants: dict[str, Participant]
    rounds: list[list[BracketMatch]]
    champion: str | None = None

    # Creation
    @classmethod
    def create(cls, catalog: Catalog, *, name: str, groups: list[str], size: int, category: str = "",
               include_human: bool = False, team_size: int = 1, map_name: str = "DFH Stadium",
               installed_only: bool = False, rng: random.Random | None = None) -> "Tournament":
        if size < 2:
            raise ValueError("البطولة تحتاج مشاركَين على الأقل.")
        rng = rng or random.Random()
        pool = select_bots(catalog, groups, category, installed_only)
        need = size - (1 if include_human else 0)
        rng.shuffle(pool)
        # Keep rank spread: sort the shuffled pool by rank band so picks cover the chosen groups.
        picked = spread_pick(pool, need)
        parts: list[Participant] = [_participant(e) for e in picked]
        fill_idx = [i for g in groups for i, r in enumerate(RANKS) if group_of(i) == g] or [0]
        while len(parts) < need:
            idx = fill_idx[len(parts) % len(fill_idx)]
            skill = psyonix_for_rank(idx)
            parts.append(Participant(f"psyonix-{len(parts)}", f"Psyonix {skill} #{len(parts) + 1}", "psyonix",
                                     RANKS[idx], idx, "Non-Mechanical", "Psyonix", psyonix_skill=skill))
        if include_human:
            parts.append(Participant(HUMAN_ID, "أنت", "human", "—", -1, "Human", "لاعب"))
        # Seed strongest first so top seeds meet late; the human is seeded mid-pack.
        parts.sort(key=lambda p: -p.rank_idx if p.kind != "human" else -math.inf)
        if include_human:
            h = parts.pop(0)
            parts.insert(len(parts) // 2, h)
        for i, p in enumerate(parts, 1):
            p.seed = i
        t = cls(id=uuid.uuid4().hex[:10], name=name, created=datetime.now().isoformat(timespec="seconds"),
                groups=groups, category=category, team_size=team_size, map_name=map_name,
                participants={p.id: p for p in parts}, rounds=[])
        t._build_bracket([p.id for p in parts])
        return t

    def _build_bracket(self, seeded: list[str]) -> None:
        n = 1 << max(1, math.ceil(math.log2(len(seeded))))
        order = seed_order(n)
        slots = [seeded[s - 1] if s <= len(seeded) else None for s in order]
        total = int(math.log2(n))
        self.rounds = [[BracketMatch(f"r{r}m{i}", r, i) for i in range(n >> (r + 1))] for r in range(total)]
        for i, m in enumerate(self.rounds[0]):
            m.a, m.b = slots[2 * i], slots[2 * i + 1]
        for m in self.rounds[0]:
            if (m.a is None) != (m.b is None):
                self._set_winner(m, m.a or m.b)

    # Results
    def match(self, match_id: str) -> BracketMatch:
        for rnd in self.rounds:
            for m in rnd:
                if m.id == match_id:
                    return m
        raise KeyError(match_id)

    def record(self, match_id: str, score_a: int, score_b: int, simulated: bool = False) -> None:
        m = self.match(match_id)
        if not m.ready:
            raise ValueError("هذه المباراة غير جاهزة أو انتهت.")
        if score_a == score_b:
            raise ValueError("لا يوجد تعادل في الأدوار الإقصائية.")
        m.score_a, m.score_b, m.simulated = score_a, score_b, simulated
        m.played_at = datetime.now().isoformat(timespec="seconds")
        self._set_winner(m, m.a if score_a > score_b else m.b)

    def _set_winner(self, m: BracketMatch, winner: str | None) -> None:
        m.winner = winner
        if m.round + 1 >= len(self.rounds):
            self.champion = winner
            return
        nxt = self.rounds[m.round + 1][m.index // 2]
        if m.index % 2 == 0:
            nxt.a = winner
        else:
            nxt.b = winner

    def next_match(self) -> BracketMatch | None:
        for rnd in self.rounds:
            for m in rnd:
                if m.ready:
                    return m
        return None

    def spec_for(self, m: BracketMatch) -> MatchSpec:
        a, b = self.participants[m.a], self.participants[m.b]
        slots = []
        for team, p in ((0, a), (1, b)):
            for k in range(self.team_size):
                # Human plays with copies of nothing: in team modes the human's teammates are Psyonix bots.
                if p.kind == "human" and k > 0:
                    slots.append(Slot("psyonix", team, f"Psyonix {psyonix_for_rank(10)}", psyonix_skill="Pro"))
                else:
                    slots.append(p.slot(team))
        return MatchSpec(slots=slots, map_name=self.map_name)

    def simulate(self, m: BracketMatch, rng: random.Random | None = None, ratings: dict[str, float] | None = None) -> None:
        """Quick result from rank strength (Elo expectation). Marked simulated; not a real match."""
        rng = rng or random.Random()
        ra, rb = (self._strength(self.participants[x], ratings) for x in (m.a, m.b))
        p_a = 1 / (1 + 10 ** ((rb - ra) / 400))
        win_a = rng.random() < p_a
        loser = rng.randint(0, 3)
        winner = loser + rng.randint(1, 3)
        self.record(m.id, winner if win_a else loser, loser if win_a else winner, simulated=True)

    @staticmethod
    def _strength(p: Participant, ratings: dict[str, float] | None) -> float:
        if ratings and p.id in ratings:
            return ratings[p.id]
        return rank_to_rating(max(p.rank_idx, 0))

    # Stats
    def stats(self) -> list[dict]:
        rows = {pid: {"participant": p, "w": 0, "l": 0, "gf": 0, "ga": 0, "log": []} for pid, p in self.participants.items()}
        total = len(self.rounds)
        for rnd in self.rounds:
            for m in rnd:
                if m.score_a is None or m.a is None or m.b is None:
                    continue
                for me, opp, gf, ga in ((m.a, m.b, m.score_a, m.score_b), (m.b, m.a, m.score_b, m.score_a)):
                    r = rows[me]
                    r["gf"] += gf
                    r["ga"] += ga
                    r["w" if m.winner == me else "l"] += 1
                    r["log"].append({"round": round_name(m.round, total), "opponent": self.participants[opp].name,
                                     "score": f"{gf}-{ga}", "won": m.winner == me, "simulated": m.simulated})
        out = []
        for r in rows.values():
            games = r["w"] + r["l"]
            r["win_pct"] = (r["w"] / games) if games else 0.0
            r["eliminated"] = any(m.winner and m.winner != r["participant"].id and r["participant"].id in (m.a, m.b)
                                  for rnd in self.rounds for m in rnd)
            out.append(r)
        out.sort(key=lambda r: (-r["w"], r["l"], -(r["gf"] - r["ga"]), r["participant"].seed))
        return out

    # Persistence
    def to_dict(self) -> dict:
        d = asdict(self)
        d["participants"] = {k: asdict(v) for k, v in self.participants.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Tournament":
        d = dict(d)
        d["participants"] = {k: Participant(**v) for k, v in d["participants"].items()}
        d["rounds"] = [[BracketMatch(**m) for m in rnd] for rnd in d["rounds"]]
        return cls(**d)


def seed_order(n: int) -> list[int]:
    """Standard bracket order so seed 1 and 2 can only meet in the final: [1, n, ..., 2]."""
    order = [1]
    while len(order) < n:
        m = len(order) * 2 + 1
        order = [x for s in order for x in (s, m - s)]
    return order


def select_bots(catalog: Catalog, groups: list[str], category: str = "", installed_only: bool = False) -> list[BotEntry]:
    wanted = set(groups)
    out = []
    for e in catalog.rankable():
        if category and e.category != category:
            continue
        if installed_only and not e.installed:
            continue
        if e.rank_group in wanted and any(ch.isalnum() for ch in e.name):
            out.append(e)
    return out


def spread_pick(pool: list[BotEntry], n: int) -> list[BotEntry]:
    by_group: dict[str, list[BotEntry]] = {}
    for e in pool:
        by_group.setdefault(e.rank_group, []).append(e)
    for v in by_group.values():
        v.sort(key=lambda e: not e.installed)
    picked = []
    while len(picked) < n and any(by_group.values()):
        for g in GROUPS:
            if by_group.get(g) and len(picked) < n:
                picked.append(by_group[g].pop(0))
    return picked


def _participant(e: BotEntry) -> Participant:
    idx = e.band.mid if e.band else 0
    return Participant(e.slug, e.name, "bot", e.expected_level, idx, e.category, e.bot_type,
                       str(e.toml_path) if e.toml_path else None)


class TournamentStore:
    def __init__(self, folder: Path):
        self.folder = folder

    def save(self, t: Tournament) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / f"{t.id}.json").write_text(json.dumps(t.to_dict(), ensure_ascii=False, indent=1), "utf-8")

    def list(self) -> list[Tournament]:
        if not self.folder.exists():
            return []
        out = [Tournament.from_dict(json.loads(p.read_text("utf-8"))) for p in self.folder.glob("*.json")]
        return sorted(out, key=lambda t: t.created, reverse=True)

    def delete(self, tid: str) -> None:
        (self.folder / f"{tid}.json").unlink(missing_ok=True)


__all__ = ["Tournament", "TournamentStore", "Participant", "BracketMatch", "round_name", "seed_order", "rank_index"]
