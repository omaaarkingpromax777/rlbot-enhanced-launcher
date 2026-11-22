"""Automatic bot-vs-bot calibration.

Usage: rlbot-launcher-calibrate --bots-dir <botpack> --games 40 --mode 1v1 --out ratings.json
Needs Windows (or Linux + Proton) with Rocket League and RLBotServer installed.
"""

import argparse
import json
import random
import time
from pathlib import Path

from ..core.botpack import scan_bots
from ..core.catalog import Catalog, slugify
from ..core.match import MatchSpec, Slot
from ..core.settings import DATA_DIR
from .metrics import MatchTelemetry, is_mechanical, skill_profile
from .ratings import RatingBook

PSYONIX = ["Beginner", "Rookie", "Pro", "AllStar"]


def psyonix_slug(skill: str) -> str:
    return "psyonix-all-star" if skill == "AllStar" else f"psyonix-{skill.lower()}"


def choose_pairs(book: RatingBook, pool: list[str], n: int, rng: random.Random) -> list[tuple[str, str]]:
    """Active sampling: prefer uncertain bots against opponents with a close rating."""
    pairs = []
    for _ in range(n):
        focus = max(pool, key=lambda s: book.get(s).sigma + rng.random() * 0.5)
        mu = book.get(focus).mu
        others = sorted((s for s in pool if s != focus), key=lambda s: abs(book.get(s).mu - mu))
        pairs.append((focus, rng.choice(others[:3])))
    return pairs


def play(spec: MatchSpec, timeout_s: float = 420.0) -> tuple[tuple[int, int], dict]:
    from rlbot.managers import MatchManager

    from ..core.match import build_config

    tele = MatchTelemetry()
    mgr = MatchManager()
    mgr.ensure_server_started()
    mgr.connect(wants_match_communications=False, wants_ball_predictions=False, close_between_matches=False)
    mgr.rlbot_interface.packet_handlers.append(tele.on_packet)
    mgr.run(background_thread=True)
    mgr.start_match(build_config(spec), wait_for_start=True)
    start = time.time()
    while time.time() - start < timeout_s:
        time.sleep(1)
        pkt = mgr.packet
        if pkt is not None and str(pkt.match_info.match_phase).endswith("Ended"):
            break
    mgr.stop_match()
    mgr.disconnect()
    return tele.final_scores, tele.summary()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bots-dir", type=Path, required=True)
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--mode", choices=["1v1", "2v2", "3v3"], default="1v1")
    ap.add_argument("--launcher", default="Steam")
    ap.add_argument("--out", type=Path, default=DATA_DIR / "ratings.json")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    catalog = Catalog.bundled()
    installed = {n: p for n, p in scan_bots(args.bots_dir).items() if (e := catalog.find(n)) is None or e.in_rank_system}
    book = RatingBook.load(args.out)
    pool = {slugify(n): ("bot", n, p) for n, p in installed.items()}
    pool.update({psyonix_slug(s): ("psyonix", f"Psyonix {s}", s) for s in PSYONIX})
    size = int(args.mode[0])
    rng = random.Random(args.seed)
    profiles_path = args.out.with_name("profiles.json")
    profiles = json.loads(profiles_path.read_text("utf-8")) if profiles_path.exists() else {}

    for i, (a, b) in enumerate(choose_pairs(book, list(pool), args.games, rng), 1):
        slots = []
        for team, slug in ((0, a), (1, b)):
            kind, name, extra = pool[slug]
            for _ in range(size):
                if kind == "bot":
                    slots.append(Slot("bot", team, name, toml_path=extra))
                else:
                    slots.append(Slot("psyonix", team, name, psyonix_skill=extra))
        spec = MatchSpec(slots=slots, launcher=args.launcher, instant_start=True)
        (bg, og), summary = play(spec)
        book.record([a] * 1, [b] * 1, bg, og)
        for _idx, m in summary.items():
            slug = a if m["team"] == 0 else b
            prof = skill_profile(m)
            prev = profiles.get(slug, {"n": 0})
            n = prev["n"] + 1
            merged = {k: (prev.get(k, 0) * prev["n"] + v) / n for k, v in prof.to_dict().items()}
            merged["n"] = n
            merged["mechanical"] = is_mechanical(prof)
            profiles[slug] = merged
        book.save(args.out)
        profiles_path.write_text(json.dumps(profiles, indent=2), "utf-8")
        print(f"[{i}/{args.games}] {a} {bg}-{og} {b}")

    for slug, d in sorted(book.export().items(), key=lambda kv: -kv[1]["mu"]):
        print(f"{slug:28s} mu={d['mu']:.1f} sigma={d['sigma']:.2f} games={d['games']:3d} rank={d['rank'] or 'غير مصنف'}")


if __name__ == "__main__":
    main()
