"""Rank Challenge: beat a share of the bots in a rank group to advance to the next group, up to SSL."""

from dataclasses import asdict, dataclass, field

from .catalog import Catalog
from .ranks import GROUPS, RANKS


@dataclass
class ChallengeGame:
    group: str
    opponent: str
    goals_for: int
    goals_against: int

    @property
    def won(self) -> bool:
        return self.goals_for > self.goals_against


@dataclass
class RankChallenge:
    group: str = "Bronze"
    target: str = "Supersonic Legend"
    opponents_per_group: int = 5
    pass_ratio: float = 0.6
    category: str = ""
    opponents: list[str] = field(default_factory=list)
    games: list[ChallengeGame] = field(default_factory=list)
    finished: bool = False

    def setup(self, catalog: Catalog) -> None:
        """Pick this group's opponents: installed bots first, then the rest of the group."""
        bots = [e for e in catalog.rankable() if e.rank_group == self.group and any(c.isalnum() for c in e.name)
                and (not self.category or e.category == self.category)]
        if not bots:
            # No bot is centred in this group (e.g. SSL): use the bots whose band reaches it.
            first = RANKS.index(f"{self.group} 1") if self.group != GROUPS[-1] else len(RANKS) - 1
            bots = [e for e in catalog.rankable() if e.band and e.band.high >= first
                    and any(c.isalnum() for c in e.name) and (not self.category or e.category == self.category)]
        bots.sort(key=lambda e: (not e.installed, e.name))
        self.opponents = [e.name for e in bots[: self.opponents_per_group]]

    def current_games(self) -> list[ChallengeGame]:
        return [g for g in self.games if g.group == self.group]

    @property
    def needed_wins(self) -> int:
        n = max(len(self.opponents), 1)
        return max(1, -(-int(self.pass_ratio * 100) * n // 100))

    def next_opponent(self) -> str | None:
        played = {g.opponent for g in self.current_games()}
        for name in self.opponents:
            if name not in played:
                return name
        return None

    def record(self, opponent: str, goals_for: int, goals_against: int, catalog: Catalog) -> str:
        """Returns 'promoted', 'failed', 'champion' or 'continue'."""
        self.games.append(ChallengeGame(self.group, opponent, goals_for, goals_against))
        cur = self.current_games()
        wins = sum(g.won for g in cur)
        remaining = len(self.opponents) - len(cur)
        if wins >= self.needed_wins:
            if self.group == self.target or self.group == GROUPS[-1]:
                self.finished = True
                return "champion"
            self.group = GROUPS[GROUPS.index(self.group) + 1]
            self.setup(catalog)
            return "promoted"
        if wins + remaining < self.needed_wins:
            # Retry the same group with a fresh run.
            self.games = [g for g in self.games if g.group != self.group]
            return "failed"
        return "continue"

    def progress(self) -> tuple[int, int, int]:
        cur = self.current_games()
        return sum(g.won for g in cur), len(cur), len(self.opponents)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RankChallenge":
        d = dict(d)
        d["games"] = [ChallengeGame(**g) for g in d.get("games", [])]
        return cls(**d)
