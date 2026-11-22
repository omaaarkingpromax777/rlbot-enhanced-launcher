import json
from pathlib import Path

import pytest

from rlbot_launcher.calibration.metrics import is_mechanical, skill_profile
from rlbot_launcher.calibration.ratings import RatingBook
from rlbot_launcher.core import botpack, game_detect, multiplayer as mp
from rlbot_launcher.core.catalog import Catalog
from rlbot_launcher.core.match import MatchSpec, Slot, build_config
from rlbot_launcher.core.ranks import RANKS, parse_band, rank_index, rating_to_rank
from rlbot_launcher.core.settings import Settings
from rlbot_launcher.core.training import Ladder, estimate_player_rank


def test_ranks_full_ladder():
    assert len(RANKS) == 22 and RANKS[0] == "Bronze 1" and RANKS[-1] == "Supersonic Legend"
    assert rank_index("SSL") == 21
    b = parse_band("Silver 2 – Diamond 1")
    assert (b.low, b.high) == (rank_index("Silver 2"), rank_index("Diamond 1"))
    assert parse_band("Grand Champion 1 – SSL (غير مقاس)").high == 21
    assert rating_to_rank(-50) == 0 and rating_to_rank(1e9) == 21


def test_catalog_bundled_and_filters():
    c = Catalog.bundled()
    assert len(c.entries) >= 100
    mech = c.filter(category="Mechanical")
    assert mech and all(e.is_mechanical for e in mech)
    assert all(e.rank_group == "Gold" for e in c.filter(group="Gold"))
    for i in range(len(RANKS)):
        for e in c.for_rank(i):
            assert e.band.contains(i)


def test_scan_bots_and_attach(tmp_path: Path):
    d = tmp_path / "MyBot"
    d.mkdir()
    (d / "bot.toml").write_text('[settings]\nname = "Nexto"\nrun_command = "x.exe"\nagent_id = "a/b"\n')
    (tmp_path / "new.bot.toml").write_text('[settings]\nname = "BrandNewBot"\n')
    found = botpack.scan_bots(tmp_path)
    assert set(found) == {"Nexto", "BrandNewBot"}
    c = Catalog.bundled()
    c.attach_installed(found)
    assert c.find("Nexto").installed and c.find("BrandNewBot").source == "Local"


def test_build_match_config(tmp_path: Path):
    (tmp_path / "bot.toml").write_text('[settings]\nname = "Nexto"\nrun_command = "x.exe"\nagent_id = "a/b"\n')
    spec = MatchSpec(slots=[Slot("human", 0), Slot("bot", 1, "Nexto", toml_path=tmp_path / "bot.toml"),
                            Slot("psyonix", 1, "Psyonix Pro", psyonix_skill="Pro")], map_name="Mannfield")
    assert spec.validate() == []
    cfg = build_config(spec)
    assert cfg.game_map_upk == "EuroStadium_P"
    assert len(cfg.player_configurations) == 3


def test_validate_errors():
    errs = MatchSpec(slots=[Slot("human", 0), Slot("human", 1), Slot("bot", 1, "X")]).validate()
    assert len(errs) == 2


def test_steam_detection(tmp_path: Path):
    lib = tmp_path / "lib"
    (lib / "steamapps").mkdir(parents=True)
    (lib / "steamapps" / "appmanifest_252950.acf").write_text("")
    root = tmp_path / "Steam"
    (root / "steamapps").mkdir(parents=True)
    (root / "steamapps" / "libraryfolders.vdf").write_text(f'"libraryfolders" {{ "1" {{ "path" "{lib}" }} }}')
    g = game_detect.find_steam([root])
    assert g and g.launcher == "Steam" and g.path == lib / "steamapps" / "common" / "rocketleague"


def test_epic_detection(tmp_path: Path):
    (tmp_path / "a.item").write_text(json.dumps({"DisplayName": "Rocket League®", "InstallLocation": "D:/RL"}))
    assert game_detect.find_epic(tmp_path).path == Path("D:/RL")


def test_multiplayer_helpers():
    assert mp.join_command("1.2.3.4:7777", "pw") == "open 1.2.3.4:7777?Lan?Password=pw"
    lobbies = [mp.Lobby("1", "EU-HEL-RLBOT:7836", "Stadium_P", 2, False, "1.1.1.1", 7836),
               mp.Lobby("2", "ME-DXB Diamond", "Park_P", 1, True, "2.2.2.2", 7000)]
    assert mp.find_lobby(lobbies, "me-dxb diamond").id == "2"
    assert mp.sort_by_region_priority(lobbies, "ME")[0].id == "2"
    assert mp._lobby_list({"lobbies": [{"a": 1}]}) == [{"a": 1}]
    req = mp.HostRequest(mp.RHostServer("1.1.1.1", "80", "EU-HEL"), "Stadium_P", ["nexto"], ["nexto"], session_name="x", password="y")
    assert "blueBots=nexto" in req.url() and "lobbyName=x" in req.url()


def test_ladder_promotes_and_demotes():
    lad = Ladder(start=0, end=5)
    lad.record(3, 1)
    assert lad.current == 0
    lad.record(2, 0)
    assert lad.current == 1
    lad.record(0, 2)
    lad.record(0, 3)
    assert lad.current == 0
    assert estimate_player_rank(lad.history) in RANKS


def test_rating_book_maps_anchors(tmp_path: Path):
    book = RatingBook()
    import random
    rng = random.Random(1)
    strength = {"psyonix-beginner": 0, "psyonix-rookie": 2, "psyonix-pro": 5, "psyonix-all-star": 7, "nexto": 18, "midbot": 11}
    names = list(strength)
    for _ in range(1200):
        a, b = rng.sample(names, 2)
        pa = 1 / (1 + 10 ** ((strength[b] - strength[a]) / 4))
        if rng.random() < pa:
            book.record([a], [b], 2, 1)
        else:
            book.record([a], [b], 1, 2)
    r = book.rank_of("midbot")
    assert r is not None and rank_index("Gold 1") < rank_index(r) < rank_index("Grand Champion 1")
    book.save(tmp_path / "r.json")
    assert RatingBook.load(tmp_path / "r.json").games["midbot"] == book.games["midbot"]


def test_skill_profile_mechanical():
    m = dict(avg_speed=1500, supersonic_pct=0.25, goal_side_pct=0.7, air_pct=0.4, recovery_s=0.8, touches_pm=12,
             aerial_touches_pm=5, forward_touch_pct=0.7, avg_touch_height=500, air_dribble_chain_max=4,
             boost_pm=300, shot_accuracy=0.5, goals=2, shots=4, saves=1)
    assert is_mechanical(skill_profile(m))
    m.update(aerial_touches_pm=0.2, avg_touch_height=120, air_dribble_chain_max=0)
    assert not is_mechanical(skill_profile(m))


def test_settings_roundtrip(tmp_path: Path):
    s = Settings(preferred_region="ME", favorites=[{"name": "x"}])
    s.save(tmp_path / "s.json")
    assert Settings.load(tmp_path / "s.json").favorites == [{"name": "x"}]


@pytest.mark.parametrize("name", ["Nexto", "nexto"])
def test_find_case_insensitive(name):
    assert Catalog.bundled().find(name) is not None
