from dataclasses import dataclass

TIERS = [
    "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Champion", "Grand Champion",
]
RANKS: list[str] = [f"{t} {d}" for t in TIERS for d in (1, 2, 3)] + ["Supersonic Legend"]
GROUPS: list[str] = TIERS + ["Supersonic Legend"]

GROUP_COLORS = {
    "Bronze": "#b07a4a",
    "Silver": "#a9b4c2",
    "Gold": "#e2b43b",
    "Platinum": "#4fc3c9",
    "Diamond": "#4a7cf0",
    "Champion": "#a463f2",
    "Grand Champion": "#e5484d",
    "Supersonic Legend": "#f5f5f5",
}

# Internal rating scale: each of the 22 ranks spans RATING_STEP points starting at RATING_BASE.
RATING_BASE = 0.0
RATING_STEP = 100.0


@dataclass(frozen=True)
class RankBand:
    low: int
    high: int

    def contains(self, idx: int) -> bool:
        return self.low <= idx <= self.high

    @property
    def mid(self) -> int:
        return (self.low + self.high) // 2

    def label(self) -> str:
        if self.low == self.high:
            return RANKS[self.low]
        return f"{RANKS[self.low]} – {RANKS[self.high]}"


def rank_index(name: str) -> int:
    name = name.strip()
    if name.startswith("SSL") or name.startswith("Supersonic"):
        return len(RANKS) - 1
    for i, r in enumerate(RANKS):
        if name.startswith(r):
            return i
    for i, r in enumerate(RANKS):
        if name.startswith(r.rsplit(" ", 1)[0]):
            return i
    raise ValueError(f"Unknown rank: {name!r}")


def group_of(idx: int) -> str:
    return RANKS[idx].rsplit(" ", 1)[0] if idx < len(RANKS) - 1 else "Supersonic Legend"


def parse_band(text: str) -> RankBand | None:
    """Parse labels like 'Silver 2 – Diamond 1', 'Bronze 1', 'Grand Champion 1 – SSL (...)'."""
    if not text or text == "—":
        return None
    if "قابل للضبط" in text or "adjustable" in text.lower():
        return RankBand(0, rank_index("Grand Champion 1"))
    parts = [p.split("(")[0].strip() for p in text.replace("-", "–").split("–")]
    parts = [p for p in parts if p]
    try:
        lo = rank_index(parts[0])
        hi = rank_index(parts[1]) if len(parts) > 1 else lo
    except (ValueError, IndexError):
        return None
    if "Bronze (" in text:
        hi = rank_index("Bronze 3")
    return RankBand(min(lo, hi), max(lo, hi))


def rating_to_rank(rating: float) -> int:
    idx = int((rating - RATING_BASE) // RATING_STEP)
    return max(0, min(len(RANKS) - 1, idx))


def rank_to_rating(idx: int) -> float:
    return RATING_BASE + RATING_STEP * (idx + 0.5)
