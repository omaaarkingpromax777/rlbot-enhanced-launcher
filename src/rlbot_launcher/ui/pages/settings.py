from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from ...core import game_detect
from ...core.multiplayer import REGIONS
from ..common import card, header


def _path_row(edit: QLineEdit, title: str, folder: bool = True) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(edit, 1)
    b = QPushButton("استعراض…")

    def pick():
        p = QFileDialog.getExistingDirectory(w, title) if folder else QFileDialog.getOpenFileName(w, title)[0]
        if p:
            edit.setText(p)

    b.clicked.connect(pick)
    lay.addWidget(b)
    return w


class SettingsPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        s = ctx.settings
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        root.addWidget(header("Settings"))

        self.game_status = QLabel()
        detect = QPushButton("اكتشاف Rocket League تلقائياً")
        game = card(self.game_status, detect, title="Rocket League")
        root.addWidget(game)

        form = QFormLayout()
        self.launcher = QComboBox()
        self.launcher.addItems(["Steam", "Epic", "Custom", "NoLaunch"])
        self.launcher.setCurrentText(s.launcher)
        self.rl_path = QLineEdit(s.rocket_league_path)
        self.rl_path.setPlaceholderText("فارغ = اكتشاف تلقائي")
        self.server = QLineEdit(s.rlbot_server_path)
        self.server.setPlaceholderText("فارغ = تنزيل/اكتشاف تلقائي بواسطة RLBot")
        self.botpack = QLineEdit(s.botpack_dir)
        self.auto_update = QCheckBox("تحديث البوتات تلقائياً عند التشغيل")
        self.auto_update.setChecked(s.auto_update_bots)
        self.region = QComboBox()
        for code, name in REGIONS.items():
            self.region.addItem(name, code)
        self.region.setCurrentIndex(max(0, self.region.findData(s.preferred_region)))
        self.lang = QComboBox()
        self.lang.addItem("العربية", "ar")
        self.lang.addItem("English", "en")
        self.lang.setCurrentIndex(max(0, self.lang.findData(s.language)))
        form.addRow("المشغّل", self.launcher)
        form.addRow("مسار Rocket League", _path_row(self.rl_path, "مجلد Rocket League"))
        form.addRow("RLBotServer", _path_row(self.server, "RLBotServer.exe", folder=False))
        form.addRow("مجلد البوتات", _path_row(self.botpack, "مجلد حزمة البوتات"))
        form.addRow("", self.auto_update)
        form.addRow("المنطقة المفضلة", self.region)
        form.addRow("اللغة", self.lang)
        c = card(title="التشغيل والبوتات")
        c.layout().addLayout(form)
        root.addWidget(c)

        save = QPushButton("حفظ")
        save.setObjectName("primary")
        root.addWidget(save)
        root.addStretch()
        detect.clicked.connect(self.detect)
        save.clicked.connect(self.save)
        self.render_game()

    def render_game(self):
        g = self.ctx.game
        running = game_detect.is_running()
        if g:
            self.game_status.setText(f"✓ تم العثور عليها ({g.launcher}): {g.path}" + ("  · تعمل الآن" if running else ""))
        else:
            self.game_status.setText("لم يتم العثور على Rocket League. اختر المشغّل والمسار يدوياً.")

    def detect(self):
        self.ctx.settings.rocket_league_path = ""
        self.ctx.detect_game()
        if self.ctx.game:
            self.launcher.setCurrentText(self.ctx.game.launcher)
        self.render_game()

    def save(self):
        s = self.ctx.settings
        s.launcher = self.launcher.currentText()
        s.rocket_league_path = self.rl_path.text().strip()
        s.rlbot_server_path = self.server.text().strip()
        s.botpack_dir = self.botpack.text().strip() or s.botpack_dir
        s.auto_update_bots = self.auto_update.isChecked()
        s.preferred_region = self.region.currentData()
        s.language = self.lang.currentData()
        s.save()
        self.ctx.runner.__init__(s.rlbot_server_path)
        self.ctx.refresh_installed()
        self.ctx.bus.status.emit("تم حفظ الإعدادات.")
