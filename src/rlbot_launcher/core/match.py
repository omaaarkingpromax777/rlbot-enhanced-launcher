"""Build an RLBot v5 MatchConfiguration from the launcher's simple match description and run it."""

import threading
from dataclasses import dataclass, field
from pathlib import Path

MAPS = {
    "DFH Stadium": "Stadium_P",
    "Mannfield": "EuroStadium_P",
    "Champions Field": "cs_p",
    "Urban Central": "TrainStation_P",
    "Beckwith Park": "Park_P",
    "Utopia Coliseum": "UtopiaStadium_P",
    "Wasteland": "wasteland_s_p",
    "Neo Tokyo": "NeoTokyo_Standard_P",
    "AquaDome": "Underwater_P",
    "Salty Shores": "beach_P",
    "Forbidden Temple": "CHN_Stadium_P",
    "Deadeye Canyon": "Outlaw_P",
}

PSYONIX_SKILLS = ("Beginner", "Rookie", "Pro", "AllStar")


@dataclass
class Slot:
    kind: str  # human | bot | psyonix
    team: int  # 0 blue, 1 orange
    name: str = ""
    toml_path: Path | None = None
    psyonix_skill: str = "AllStar"


@dataclass
class MatchSpec:
    slots: list[Slot] = field(default_factory=list)
    map_name: str = "DFH Stadium"
    launcher: str = "Steam"
    launcher_arg: str = ""
    game_mode: str = "Soccar"
    unlimited_time: bool = False
    instant_start: bool = False
    enable_state_setting: bool = True

    def validate(self) -> list[str]:
        errors = []
        if not self.slots:
            errors.append("لا يوجد لاعبون في المباراة.")
        if sum(1 for s in self.slots if s.kind == "human") > 1:
            errors.append("مسموح بلاعب بشري واحد على هذا الجهاز.")
        for s in self.slots:
            if s.kind == "bot" and (s.toml_path is None or not Path(s.toml_path).exists()):
                errors.append(f"البوت {s.name} غير مثبت.")
        if self.map_name not in MAPS:
            errors.append(f"ملعب غير معروف: {self.map_name}")
        return errors


def psyonix_for_rank(rank_idx: int) -> str:
    """Rough mapping used when no installed RLBot bot covers a rank."""
    if rank_idx <= 1:
        return "Beginner"
    if rank_idx <= 3:
        return "Rookie"
    if rank_idx <= 5:
        return "Pro"
    return "AllStar"


def build_config(spec: MatchSpec):
    from rlbot import flat
    from rlbot.config import load_player_config

    players = []
    for s in spec.slots:
        if s.kind == "human":
            players.append(flat.PlayerConfiguration(flat.Human(), s.team))
        elif s.kind == "psyonix":
            skill = getattr(flat.PsyonixSkill, s.psyonix_skill)
            players.append(flat.PlayerConfiguration(flat.PsyonixBot(s.name or f"Psyonix {s.psyonix_skill}", None, skill), s.team, 0))
        else:
            players.append(load_player_config(Path(s.toml_path), s.team, s.name or None))

    mutators = flat.MutatorSettings(
        match_length=flat.MatchLengthMutator.Unlimited if spec.unlimited_time else flat.MatchLengthMutator.FiveMinutes,
    )
    return flat.MatchConfiguration(
        launcher=getattr(flat.Launcher, spec.launcher),
        launcher_arg=spec.launcher_arg,
        auto_start_agents=True,
        wait_for_agents=True,
        game_map_upk=MAPS[spec.map_name],
        player_configurations=players,
        script_configurations=[],
        game_mode=getattr(flat.GameMode, spec.game_mode),
        skip_replays=True,
        instant_start=spec.instant_start,
        mutators=mutators,
        existing_match_behavior=flat.ExistingMatchBehavior.Restart,
        enable_rendering=flat.DebugRendering.OffByDefault,
        enable_state_setting=spec.enable_state_setting,
        freeplay=False,
    )


class MatchRunner:
    """Owns one rlbot MatchManager; all calls are safe to make from a worker thread."""

    def __init__(self, server_path: str = ""):
        self._server_path = Path(server_path) if server_path else None
        self._mgr = None
        self._lock = threading.Lock()

    def _manager(self):
        from rlbot.managers import MatchManager

        if self._mgr is None:
            self._mgr = MatchManager(self._server_path)
        return self._mgr

    def start(self, spec: MatchSpec) -> None:
        errors = spec.validate()
        if errors:
            raise ValueError("\n".join(errors))
        with self._lock:
            self._manager().start_match(build_config(spec), wait_for_start=False)

    def play_to_end(self, spec: MatchSpec, timeout_s: float = 900.0, on_packet=None) -> tuple[int, int]:
        """Start a match, block until Rocket League reports it ended, return (blue, orange) goals."""
        import time

        errors = spec.validate()
        if errors:
            raise ValueError("\n".join(errors))
        with self._lock:
            mgr = self._manager()
            mgr.ensure_server_started()
            if not mgr.rlbot_interface.is_connected:
                mgr.connect(wants_match_communications=False, wants_ball_predictions=False,
                            close_between_matches=False)
                mgr.run(background_thread=True)
            if on_packet and on_packet not in mgr.rlbot_interface.packet_handlers:
                mgr.rlbot_interface.packet_handlers.append(on_packet)
            mgr.packet = None
            mgr.start_match(build_config(spec), wait_for_start=True)
        start = time.time()
        scores = (0, 0)
        try:
            while time.time() - start < timeout_s:
                time.sleep(0.5)
                pkt = mgr.packet
                if pkt is None:
                    continue
                if len(pkt.teams) >= 2:
                    scores = (pkt.teams[0].score, pkt.teams[1].score)
                if str(pkt.match_info.match_phase).endswith("Ended"):
                    return scores
            raise TimeoutError("انتهى الوقت قبل نهاية المباراة")
        finally:
            if on_packet and on_packet in mgr.rlbot_interface.packet_handlers:
                mgr.rlbot_interface.packet_handlers.remove(on_packet)

    def console(self, command: str) -> None:
        with self._lock:
            mgr = self._manager()
            mgr.ensure_server_started()
            if not mgr.rlbot_interface.is_connected:
                mgr.connect(wants_match_communications=False, wants_ball_predictions=False,
                            close_between_matches=False)
                mgr.run(background_thread=True)
            mgr.send_console_command(command)

    def stop(self) -> None:
        with self._lock:
            if self._mgr is not None:
                self._mgr.stop_match()
