import random

import pytest

from rlbot_launcher.core.catalog import Catalog
from rlbot_launcher.core.challenge import RankChallenge
from rlbot_launcher.core.tournament import HUMAN_ID, Tournament, TournamentStore, round_name, seed_order


def test_seed_order():
    assert seed_order(8) == [1, 8, 4, 5, 2, 7, 3, 6]


@pytest.mark.parametrize("size", [4, 6, 8, 16])
def test_tournament_runs_to_champion(size, tmp_path):
    cat = Catalog.bundled()
    t = Tournament.create(cat, name="t", groups=["Diamond", "Champion"], size=size, rng=random.Random(size))
    assert len(t.participants) == size
    assert {p.rank.split()[0] for p in t.participants.values() if p.kind == "bot"} <= {"Diamond", "Platinum", "Gold", "Champion", "Grand", "Silver"}
    rng = random.Random(1)
    while (m := t.next_match()) is not None:
        t.simulate(m, rng)
    assert t.champion in t.participants
    stats = t.stats()
    assert stats[0]["participant"].id == t.champion
    assert sum(r["w"] for r in stats) == sum(r["l"] for r in stats)
    store = TournamentStore(tmp_path)
    store.save(t)
    loaded = store.list()[0]
    assert loaded.champion == t.champion and loaded.rounds[-1][0].winner == t.champion


def test_round_names_and_human():
    t = Tournament.create(Catalog.bundled(), name="h", groups=["Gold"], size=8, include_human=True, rng=random.Random(0))
    assert HUMAN_ID in t.participants
    assert [round_name(i, len(t.rounds)) for i in range(3)] == ["ربع النهائي", "نصف النهائي", "النهائي"]
    m = next(m for m in t.rounds[0] if HUMAN_ID in (m.a, m.b))
    spec = t.spec_for(m)
    assert sum(s.kind == "human" for s in spec.slots) == 1
    with pytest.raises(ValueError):
        t.record(m.id, 2, 2)
    t.record(m.id, 3, 1)
    assert m.winner == m.a


def test_category_filter():
    t = Tournament.create(Catalog.bundled(), name="m", groups=["Champion", "Grand Champion"], size=4,
                          category="Mechanical", rng=random.Random(0))
    assert all(p.category == "Mechanical" for p in t.participants.values() if p.kind == "bot")


def test_rank_challenge_promotes_to_ssl():
    cat = Catalog.bundled()
    ch = RankChallenge(group="Diamond", opponents_per_group=3, pass_ratio=0.6)
    ch.setup(cat)
    assert ch.needed_wins == 2
    seen = []
    while not ch.finished:
        opp = ch.next_opponent()
        assert opp is not None, ch.group
        res = ch.record(opp, 3, 1, cat)
        seen.append(res)
    assert seen.count("promoted") == 3 and seen[-1] == "champion"


def test_rank_challenge_fail_resets():
    cat = Catalog.bundled()
    ch = RankChallenge(group="Gold", opponents_per_group=3, pass_ratio=0.67)
    ch.setup(cat)
    ch.record(ch.next_opponent(), 0, 2, cat)
    assert ch.record(ch.next_opponent(), 0, 1, cat) == "failed"
    assert ch.current_games() == [] and ch.group == "Gold"
