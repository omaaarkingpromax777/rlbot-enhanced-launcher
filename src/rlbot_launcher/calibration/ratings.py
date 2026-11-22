"""OpenSkill ratings for bots, mapped onto the 22-rank ladder through anchor bots."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from openskill.models import PlackettLuce

from ..core.ranks import RANKS, rank_index, rating_to_rank

MIN_GAMES = 40
MAX_SIGMA = 2.5

# Fixed anchors: bots whose rank is pinned so the scale lines up with human ranks.
# Values are starting assumptions; human calibration sessions replace them.
DEFAULT_ANCHORS = {
    "psyonix-beginner": "Bronze 1",
    "psyonix-rookie": "Bronze 3",
    "psyonix-pro": "Silver 2",
    "psyonix-all-star": "Gold 1",
    "nexto": "Grand Champion 1",
}


@dataclass
class RatingBook:
    model: PlackettLuce = field(default_factory=PlackettLuce)
    ratings: dict = field(default_factory=dict)
    games: dict[str, int] = field(default_factory=dict)
    anchors: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ANCHORS))

    def get(self, slug: str):
        if slug not in self.ratings:
            self.ratings[slug] = self.model.rating(name=slug)
        return self.ratings[slug]

    def record(self, blue: list[str], orange: list[str], blue_goals: int, orange_goals: int) -> None:
        teams = [[self.get(s) for s in blue], [self.get(s) for s in orange]]
        if blue_goals == orange_goals:
            ranks = [1, 1]
        else:
            ranks = [1, 2] if blue_goals > orange_goals else [2, 1]
        new = self.model.rate(teams, ranks=ranks)
        for slug, r in zip(blue + orange, new[0] + new[1]):
            self.ratings[slug] = r
            self.games[slug] = self.games.get(slug, 0) + 1

    def _linear_map(self):
        """Least-squares fit rank_index = a * mu + b over anchors that have been rated."""
        pts = [(self.ratings[s].mu, rank_index(r)) for s, r in self.anchors.items() if s in self.ratings]
        if len(pts) < 2:
            return None
        n = len(pts)
        mx = sum(p[0] for p in pts) / n
        my = sum(p[1] for p in pts) / n
        var = sum((p[0] - mx) ** 2 for p in pts)
        if var == 0:
            return None
        a = sum((p[0] - mx) * (p[1] - my) for p in pts) / var
        return a, my - a * mx

    def rank_of(self, slug: str) -> str | None:
        r = self.ratings.get(slug)
        if r is None or self.games.get(slug, 0) < MIN_GAMES or r.sigma > MAX_SIGMA:
            return None
        fit = self._linear_map()
        if fit is None:
            return None
        a, b = fit
        idx = round(a * r.mu + b)
        return RANKS[max(0, min(len(RANKS) - 1, idx))]

    def export(self) -> dict[str, dict]:
        out = {}
        for slug, r in self.ratings.items():
            out[slug] = {"mu": r.mu, "sigma": r.sigma, "games": self.games.get(slug, 0),
                         "rating": r.ordinal(), "rank": self.rank_of(slug)}
        return out

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"anchors": self.anchors, "bots": self.export()}, indent=2), "utf-8")

    @classmethod
    def load(cls, path: Path) -> "RatingBook":
        book = cls()
        if not path.exists():
            return book
        data = json.loads(path.read_text("utf-8"))
        book.anchors = data.get("anchors", book.anchors)
        for slug, d in data.get("bots", {}).items():
            book.ratings[slug] = book.model.rating(mu=d["mu"], sigma=d["sigma"], name=slug)
            book.games[slug] = d.get("games", 0)
        return book


__all__ = ["RatingBook", "rating_to_rank"]
