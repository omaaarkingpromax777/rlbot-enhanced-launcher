"""Training ladder: step through ranks from Bronze 1 to SSL, adjusting difficulty from results."""

from dataclasses import dataclass, field

from .ranks import RANKS, rank_to_rating, rating_to_rank


@dataclass
class TrainingResult:
    rank_idx: int
    goals_for: int
    goals_against: int

    @property
    def won(self) -> bool:
        return self.goals_for > self.goals_against


@dataclass
class Ladder:
    start: int = 0
    end: int = len(RANKS) - 1
    current: int = 0
    wins_to_promote: int = 2
    losses_to_demote: int = 2
    history: list[TrainingResult] = field(default_factory=list)
    _streak: int = 0

    def __post_init__(self):
        self.current = max(self.start, min(self.current, self.end))

    def record(self, goals_for: int, goals_against: int) -> int:
        res = TrainingResult(self.current, goals_for, goals_against)
        self.history.append(res)
        if res.won:
            self._streak = self._streak + 1 if self._streak > 0 else 1
            if self._streak >= self.wins_to_promote:
                self.raise_difficulty()
        elif goals_for < goals_against:
            self._streak = self._streak - 1 if self._streak < 0 else -1
            if -self._streak >= self.losses_to_demote:
                self.lower_difficulty()
        return self.current

    def raise_difficulty(self) -> int:
        self.current = min(self.end, self.current + 1)
        self._streak = 0
        return self.current

    def lower_difficulty(self) -> int:
        self.current = max(self.start, self.current - 1)
        self._streak = 0
        return self.current

    @property
    def completed(self) -> bool:
        return self.current == self.end and any(r.won and r.rank_idx == self.end for r in self.history)


def estimate_player_rating(results: list[TrainingResult], prior: float | None = None) -> float:
    """Elo-style estimate against bots whose rating is the middle of their rank band."""
    rating = prior if prior is not None else rank_to_rating(0)
    k = 60.0
    for r in results:
        opp = rank_to_rating(r.rank_idx)
        expected = 1 / (1 + 10 ** ((opp - rating) / 400))
        score = 1.0 if r.won else 0.0 if r.goals_for < r.goals_against else 0.5
        margin = 1 + min(abs(r.goals_for - r.goals_against), 4) * 0.15
        rating += k * margin * (score - expected)
    return rating


def estimate_player_rank(results: list[TrainingResult], prior: float | None = None) -> str:
    return RANKS[rating_to_rank(estimate_player_rating(results, prior))]
