from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QStatusBar,
    QVBoxLayout, QWidget,
)

from .. import APP_NAME, __version__
from .pages.bots import BotsPage
from .pages.multiplayer import MultiplayerPage
from .pages.play import PlayPage
from .pages.settings import SettingsPage
from .pages.tournaments import TournamentsPage
from .pages.training import TrainingPage

SECTIONS = [("Play", PlayPage), ("Tournaments", TournamentsPage), ("Bots", BotsPage), ("Training", TrainingPage),
            ("Multiplayer", MultiplayerPage), ("Settings", SettingsPage)]


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(APP_NAME)
        self.resize(1320, 820)
        root = QWidget()
        root.setObjectName("root")
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(240)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 12)
        brand = QLabel("RLBot V5\nEnhanced Launcher")
        brand.setObjectName("brand")
        sub = QLabel(f"v{__version__} · RLBot v5")
        sub.setObjectName("brandSub")
        sl.addWidget(brand)
        sl.addWidget(sub)

        self.stack = QStackedWidget()
        self.nav = QButtonGroup(self)
        self.pages = {}
        for i, (name, cls) in enumerate(SECTIONS):
            b = QPushButton(name)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav.addButton(b, i)
            sl.addWidget(b)
            page = cls(ctx)
            self.pages[name] = page
            self.stack.addWidget(page)
        sl.addStretch()
        self.game_lbl = QLabel()
        self.game_lbl.setObjectName("brandSub")
        self.game_lbl.setWordWrap(True)
        sl.addWidget(self.game_lbl)
        self.nav.idClicked.connect(self.stack.setCurrentIndex)
        self.nav.button(0).setChecked(True)

        lay.addWidget(self.stack, 1)
        lay.addWidget(side)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        ctx.bus.status.connect(lambda m: self.statusBar().showMessage(m, 8000))
        if ctx.settings.auto_update_bots:
            self.pages["Bots"].check_updates()
        g = ctx.game
        self.game_lbl.setText(f"● Rocket League: {g.launcher}" if g else "○ Rocket League غير مكتشفة")

    def show_section(self, name: str) -> None:
        i = [n for n, _ in SECTIONS].index(name)
        self.nav.button(i).setChecked(True)
        self.stack.setCurrentIndex(i)
