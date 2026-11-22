from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..calibration.ratings import RatingBook
from ..core import botpack, game_detect
from ..core.catalog import Catalog
from ..core.match import MatchRunner
from ..core.settings import DATA_DIR, Settings


class Bus(QObject):
    catalog_changed = Signal()
    status = Signal(str)


@dataclass
class AppContext:
    settings: Settings
    catalog: Catalog
    runner: MatchRunner
    bus: Bus = field(default_factory=Bus)
    game: game_detect.GameInstall | None = None

    @classmethod
    def create(cls, settings: Settings | None = None) -> "AppContext":
        s = settings or Settings.load()
        ctx = cls(settings=s, catalog=Catalog.bundled(), runner=MatchRunner(s.rlbot_server_path))
        ctx.refresh_installed()
        ctx.detect_game()
        return ctx

    def refresh_installed(self) -> None:
        self.catalog.attach_installed(botpack.scan_bots(Path(self.settings.botpack_dir)))
        book = RatingBook.load(DATA_DIR / "ratings.json")
        self.catalog.apply_ratings({k: v for k, v in book.export().items() if v.get("rank")})
        self.bus.catalog_changed.emit()

    def detect_game(self) -> None:
        if self.settings.rocket_league_path:
            self.game = game_detect.GameInstall(self.settings.launcher, Path(self.settings.rocket_league_path))
        else:
            self.game = game_detect.detect()
            if self.game:
                self.settings.launcher = self.game.launcher
