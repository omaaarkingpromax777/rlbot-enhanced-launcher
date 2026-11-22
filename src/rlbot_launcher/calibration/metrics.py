"""Per-player performance metrics computed from RLBot v5 GamePackets (120 Hz)."""

import math
from dataclasses import asdict, dataclass, field

SUPERSONIC = 2200.0
GOAL_Y = 5120.0
AERIAL_TOUCH_Z = 300.0


@dataclass
class PlayerAccumulator:
    name: str
    team: int
    frames: int = 0
    speed_sum: float = 0.0
    supersonic_frames: int = 0
    goal_side_frames: int = 0
    air_frames: int = 0
    recovery_sum: float = 0.0
    recoveries: int = 0
    touches: int = 0
    aerial_touches: int = 0
    forward_touches: int = 0
    touch_height_sum: float = 0.0
    chain: int = 0
    chain_max: int = 0
    boost_used: float = 0.0
    _last_touch_time: float = -1.0
    _last_boost: float | None = None
    _airborne_since: float | None = None
    _last_air_touch_time: float = -10.0

    def metrics(self, seconds: float, goals: int = 0, shots: int = 0, saves: int = 0) -> dict:
        minutes = max(seconds / 60.0, 1e-6)
        f = max(self.frames, 1)
        return {
            "avg_speed": self.speed_sum / f,
            "supersonic_pct": self.supersonic_frames / f,
            "goal_side_pct": self.goal_side_frames / f,
            "air_pct": self.air_frames / f,
            "recovery_s": (self.recovery_sum / self.recoveries) if self.recoveries else 0.0,
            "touches_pm": self.touches / minutes,
            "aerial_touches_pm": self.aerial_touches / minutes,
            "forward_touch_pct": (self.forward_touches / self.touches) if self.touches else 0.0,
            "avg_touch_height": (self.touch_height_sum / self.touches) if self.touches else 0.0,
            "air_dribble_chain_max": self.chain_max,
            "boost_pm": self.boost_used / minutes,
            "shot_accuracy": (goals / shots) if shots else 0.0,
            "goals": goals,
            "shots": shots,
            "saves": saves,
        }


@dataclass
class MatchTelemetry:
    players: dict[int, PlayerAccumulator] = field(default_factory=dict)
    seconds: float = 0.0
    _start: float | None = None
    final_scores: tuple[int, int] = (0, 0)
    score_info: dict[int, tuple[int, int, int]] = field(default_factory=dict)

    def on_packet(self, packet) -> None:
        mi = packet.match_info
        if str(mi.match_phase).endswith(("Active", "Kickoff")) is False:
            return
        now = mi.seconds_elapsed
        if self._start is None:
            self._start = now
        self.seconds = now - self._start
        ball = packet.balls[0].physics if packet.balls else None
        for i, p in enumerate(packet.players):
            acc = self.players.get(i)
            if acc is None:
                acc = self.players[i] = PlayerAccumulator(p.name, p.team)
            self._update(acc, p, ball, now)
            si = p.score_info
            self.score_info[i] = (si.goals, si.shots, si.saves)
        if packet.teams:
            self.final_scores = tuple(t.score for t in packet.teams[:2])  # type: ignore[assignment]

    def _update(self, acc: PlayerAccumulator, p, ball, now: float) -> None:
        phys = p.physics
        v = phys.velocity
        speed = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
        acc.frames += 1
        acc.speed_sum += speed
        acc.supersonic_frames += 1 if p.is_supersonic or speed >= SUPERSONIC else 0
        own_goal_y = -GOAL_Y if p.team == 0 else GOAL_Y
        if ball is not None and abs(phys.location.y - own_goal_y) < abs(ball.location.y - own_goal_y):
            acc.goal_side_frames += 1
        on_ground = str(p.air_state).endswith("OnGround")
        if not on_ground:
            acc.air_frames += 1
            if acc._airborne_since is None:
                acc._airborne_since = now
        elif acc._airborne_since is not None:
            # Recovery: time from leaving the ground to landing, for air time after a touch or bump.
            if now - acc._airborne_since > 0.5:
                acc.recovery_sum += now - acc._airborne_since
                acc.recoveries += 1
            acc._airborne_since = None
            acc.chain = 0
        if acc._last_boost is not None and p.boost < acc._last_boost:
            acc.boost_used += acc._last_boost - p.boost
        acc._last_boost = p.boost
        t = p.latest_touch
        if t is not None and t.game_seconds > acc._last_touch_time + 1e-6:
            if acc._last_touch_time >= 0:
                self._touch(acc, p, t, ball)
            acc._last_touch_time = t.game_seconds

    def _touch(self, acc: PlayerAccumulator, p, t, ball) -> None:
        acc.touches += 1
        acc.touch_height_sum += t.location.z
        if t.location.z > AERIAL_TOUCH_Z and not str(p.air_state).endswith("OnGround"):
            acc.aerial_touches += 1
            acc.chain = acc.chain + 1 if t.game_seconds - acc._last_air_touch_time < 1.5 else 1
            acc.chain_max = max(acc.chain_max, acc.chain)
            acc._last_air_touch_time = t.game_seconds
        attack_dir = 1 if p.team == 0 else -1
        if ball is not None and ball.velocity.y * attack_dir > 0:
            acc.forward_touches += 1

    def summary(self) -> dict[int, dict]:
        out = {}
        for i, acc in self.players.items():
            g, s, sv = self.score_info.get(i, (0, 0, 0))
            out[i] = {"name": acc.name, "team": acc.team, **acc.metrics(self.seconds, g, s, sv)}
        return out


@dataclass
class SkillProfile:
    """0–10 scores for the attributes shown in the Bots section, derived from measured metrics."""

    speed: float
    accuracy: float
    positioning: float
    decision: float
    recovery: float
    aerial: float
    mechanics: float

    def to_dict(self) -> dict:
        return asdict(self)


def _scale(v: float, lo: float, hi: float) -> float:
    return round(max(0.0, min(10.0, (v - lo) / (hi - lo) * 10.0)), 1)


def skill_profile(m: dict) -> SkillProfile:
    recovery = 10.0 - _scale(m["recovery_s"], 0.6, 2.5) if m["recovery_s"] else 5.0
    return SkillProfile(
        speed=_scale(m["avg_speed"], 600, 1700) * 0.6 + _scale(m["supersonic_pct"], 0.02, 0.3) * 0.4,
        accuracy=_scale(m["forward_touch_pct"], 0.3, 0.8) * 0.6 + _scale(m["shot_accuracy"], 0.1, 0.6) * 0.4,
        positioning=_scale(m["goal_side_pct"], 0.45, 0.85),
        decision=_scale(m["touches_pm"], 3, 14) * 0.5 + _scale(m["forward_touch_pct"], 0.3, 0.8) * 0.5,
        recovery=round(recovery, 1),
        aerial=_scale(m["aerial_touches_pm"], 0.0, 6.0) * 0.7 + _scale(m["avg_touch_height"], 100, 600) * 0.3,
        mechanics=_scale(m["air_dribble_chain_max"], 0, 5) * 0.5 + _scale(m["aerial_touches_pm"], 0, 6) * 0.5,
    )


def is_mechanical(p: SkillProfile) -> bool:
    return (p.aerial + p.mechanics) / 2 >= 5.0
