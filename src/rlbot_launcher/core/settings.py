import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_data_dir

DATA_DIR = Path(user_data_dir("RLBotEnhancedLauncher", appauthor=False))


@dataclass
class Settings:
    launcher: str = "Steam"  # Steam | Epic | NoLaunch
    rocket_league_path: str = ""
    botpack_dir: str = str(DATA_DIR / "botpack")
    botpack_repo: str = "RLBot/botpack"
    botpack_tag: str = ""
    auto_update_bots: bool = True
    rlbot_server_path: str = ""
    preferred_region: str = "ME"
    language: str = "ar"
    player_rating: float | None = None
    favorites: list[dict] = field(default_factory=list)

    @classmethod
    def path(cls) -> Path:
        return DATA_DIR / "settings.json"

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        p = path or cls.path()
        if not p.exists():
            return cls()
        data = json.loads(p.read_text("utf-8"))
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self, path: Path | None = None) -> None:
        p = path or self.path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), "utf-8")
