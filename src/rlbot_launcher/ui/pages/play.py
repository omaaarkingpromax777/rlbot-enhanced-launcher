from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ...core.match import MAPS, MatchSpec, Slot, psyonix_for_rank
from ...core.multiplayer import REGIONS
from ...core.ranks import RANKS, rank_index
from ..common import card, header, run_bg
from ..theme import BLUE_TEAM, ORANGE_TEAM

KINDS = {"bot": "بوت RLBot", "psyonix": "بوت Psyonix", "human": "أنا (لاعب)"}
STYLE = {"": "الكل", "Mechanical": "Mechanical", "Non-Mechanical": "Non-Mechanical"}


class SlotRow(QWidget):
    def __init__(self, ctx, team: int, parent=None):
        super().__init__(parent)
        self.ctx, self.team = ctx, team
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.kind = QComboBox()
        for k, v in KINDS.items():
            self.kind.addItem(v, k)
        self.rank = QComboBox()
        self.rank.addItems(RANKS)
        self.bot = QComboBox()
        self.bot.setMinimumWidth(180)
        for w in (self.kind, self.rank, self.bot):
            lay.addWidget(w)
        self.kind.currentIndexChanged.connect(self._refresh)
        self.rank.currentIndexChanged.connect(self._refresh)
        self.style_filter = ""
        self._refresh()

    def set_rank(self, idx: int, style: str = "") -> None:
        self.style_filter = style
        self.rank.setCurrentIndex(idx)
        self._refresh()

    def _refresh(self) -> None:
        kind = self.kind.currentData()
        self.rank.setVisible(kind != "human")
        self.bot.setVisible(kind != "human")
        self.bot.clear()
        idx = self.rank.currentIndex()
        if kind == "psyonix":
            for s in ("Beginner", "Rookie", "Pro", "AllStar"):
                self.bot.addItem(f"Psyonix {s}", s)
            self.bot.setCurrentIndex(("Beginner", "Rookie", "Pro", "AllStar").index(psyonix_for_rank(idx)))
        elif kind == "bot":
            entries = self.ctx.catalog.for_rank(idx, self.style_filter or None)
            entries.sort(key=lambda e: (not e.installed, e.band.high - e.band.low, e.name))
            for e in entries:
                self.bot.addItem(e.name if e.installed else f"{e.name}  (غير مثبت)", e.name)
            if not entries:
                self.bot.addItem("لا يوجد بوت لهذه الرتبة", None)

    def slot(self) -> Slot:
        kind = self.kind.currentData()
        if kind == "human":
            return Slot("human", self.team)
        if kind == "psyonix":
            return Slot("psyonix", self.team, self.bot.currentText(), psyonix_skill=self.bot.currentData())
        e = self.ctx.catalog.find(self.bot.currentData() or "")
        return Slot("bot", self.team, e.name if e else "", toml_path=e.toml_path if e else None)

    def to_dict(self) -> dict:
        return {"kind": self.kind.currentData(), "rank": self.rank.currentIndex(), "bot": self.bot.currentData()}

    def load(self, d: dict) -> None:
        self.kind.setCurrentIndex(max(0, self.kind.findData(d.get("kind", "bot"))))
        self.rank.setCurrentIndex(d.get("rank", 0))
        i = self.bot.findData(d.get("bot"))
        if i >= 0:
            self.bot.setCurrentIndex(i)


class TeamPanel(QWidget):
    def __init__(self, ctx, team: int, parent=None):
        super().__init__(parent)
        self.ctx, self.team = ctx, team
        self.rows: list[SlotRow] = []
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        color = BLUE_TEAM if team == 0 else ORANGE_TEAM
        title = QLabel("الفريق الأزرق" if team == 0 else "الفريق البرتقالي")
        title.setStyleSheet(f"color:{color}; font-weight:700; font-size:15px;")
        self.lay.addWidget(title)
        self.lay.addStretch()

    def set_count(self, n: int) -> None:
        while len(self.rows) < n:
            r = SlotRow(self.ctx, self.team)
            self.rows.append(r)
            self.lay.insertWidget(self.lay.count() - 1, r)
        while len(self.rows) > n:
            self.rows.pop().deleteLater()


class PlayPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        root.addWidget(header("Play", "اختر الطور والفرق والبوتات ثم اضغط Start Match. التطبيق يشغّل Rocket League و RLBotServer والبوتات تلقائياً."))

        opts = QWidget()
        g = QGridLayout(opts)
        g.setContentsMargins(0, 0, 0, 0)
        self.size = QSpinBox()
        self.size.setRange(1, 4)
        self.size.setValue(1)
        self.size.setSuffix(" لاعبين لكل فريق")
        self.map = QComboBox()
        self.map.addItems(list(MAPS))
        self.region = QComboBox()
        for code, name in REGIONS.items():
            self.region.addItem(f"{name} ({code})", code)
        self.region.setCurrentIndex(max(0, self.region.findData(ctx.settings.preferred_region)))
        self.region.setToolTip("المباراة المحلية تعمل على جهازك؛ المنطقة تُستخدم في Multiplayer فقط.")
        self.unlimited = QCheckBox("وقت غير محدود")
        self.human = QCheckBox("أنا ألعب")
        self.human.setChecked(True)
        self.human_team = QComboBox()
        self.human_team.addItems(["مع الأزرق", "مع البرتقالي"])
        for i, (lbl, w) in enumerate([("حجم الفريق", self.size), ("الملعب", self.map), ("المنطقة", self.region)]):
            g.addWidget(QLabel(lbl), 0, i)
            g.addWidget(w, 1, i)
        g.addWidget(self.human, 1, 3)
        g.addWidget(self.human_team, 1, 4)
        g.addWidget(self.unlimited, 1, 5)
        root.addWidget(card(opts, title="إعداد المباراة"))

        quick = QWidget()
        q = QHBoxLayout(quick)
        q.setContentsMargins(0, 0, 0, 0)
        q.addWidget(QLabel("رتبة الخصم بضغطة واحدة:"))
        self.quick_style = QComboBox()
        for k, v in STYLE.items():
            self.quick_style.addItem(v, k)
        q.addWidget(self.quick_style)
        for grp, idx in [("Bronze", 1), ("Silver", 4), ("Gold", 7), ("Plat", 10), ("Diamond", 13), ("Champ", 16), ("GC", 19), ("SSL", 21)]:
            b = QPushButton(grp)
            b.setObjectName("chip")
            b.clicked.connect(lambda _=False, i=idx: self.quick_fill(i))
            q.addWidget(b)
        q.addStretch()
        root.addWidget(quick)

        teams = QWidget()
        t = QHBoxLayout(teams)
        t.setContentsMargins(0, 0, 0, 0)
        self.blue = TeamPanel(ctx, 0)
        self.orange = TeamPanel(ctx, 1)
        t.addWidget(card(self.blue))
        t.addWidget(card(self.orange))
        root.addWidget(teams, 1)

        actions = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("muted")
        save = QPushButton("حفظ كتشكيلة مفضلة")
        load = QPushButton("تحميل تشكيلة")
        stop = QPushButton("Stop Match")
        stop.setObjectName("danger")
        self.start_btn = QPushButton("Start Match")
        self.start_btn.setObjectName("primary")
        for w in (self.status,):
            actions.addWidget(w, 1)
        for w in (save, load, stop, self.start_btn):
            actions.addWidget(w)
        root.addLayout(actions)

        self.size.valueChanged.connect(self._resize)
        self.human.toggled.connect(self._resize)
        self.human_team.currentIndexChanged.connect(self._resize)
        self.start_btn.clicked.connect(self.start)
        stop.clicked.connect(self.stop)
        save.clicked.connect(self.save_preset)
        load.clicked.connect(self.load_preset)
        ctx.bus.catalog_changed.connect(lambda: [r._refresh() for r in self.all_rows()])
        self._resize()
        self.quick_fill(7)

    def all_rows(self) -> list[SlotRow]:
        return self.blue.rows + self.orange.rows

    def _resize(self) -> None:
        n = self.size.value()
        self.blue.set_count(n)
        self.orange.set_count(n)
        for r in self.all_rows():
            if r.kind.currentData() == "human":
                r.kind.setCurrentIndex(0)
        if self.human.isChecked():
            panel = self.blue if self.human_team.currentIndex() == 0 else self.orange
            panel.rows[0].kind.setCurrentIndex(panel.rows[0].kind.findData("human"))

    def quick_fill(self, idx: int) -> None:
        style = self.quick_style.currentData()
        for r in self.all_rows():
            if r.kind.currentData() != "human":
                r.set_rank(idx, style)

    def spec(self) -> MatchSpec:
        return MatchSpec(
            slots=[r.slot() for r in self.all_rows()],
            map_name=self.map.currentText(),
            launcher=self.ctx.settings.launcher,
            launcher_arg=self.ctx.settings.rocket_league_path if self.ctx.settings.launcher == "Custom" else "",
            unlimited_time=self.unlimited.isChecked(),
        )

    def start(self) -> None:
        spec = self.spec()
        errors = spec.validate()
        if errors:
            QMessageBox.warning(self, "لا يمكن بدء المباراة", "\n".join(errors) + "\n\nثبّت البوتات من قسم Bots أو اختر بوت Psyonix.")
            return
        self.status.setText("جارٍ تشغيل RLBotServer و Rocket League…")
        self.start_btn.setEnabled(False)
        run_bg(self.ctx.runner.start, spec, on_done=self._started, on_error=self._failed)

    def _started(self, _):
        self.start_btn.setEnabled(True)
        self.status.setText("المباراة تعمل.")

    def _failed(self, msg: str):
        self.start_btn.setEnabled(True)
        self.status.setText("فشل التشغيل.")
        QMessageBox.critical(self, "فشل بدء المباراة", msg)

    def stop(self) -> None:
        run_bg(self.ctx.runner.stop, on_done=lambda _: self.status.setText("توقفت المباراة."),
               on_error=lambda m: self.status.setText(m))

    def save_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "حفظ تشكيلة", "اسم التشكيلة:")
        if not ok or not name:
            return
        preset = {"name": name, "size": self.size.value(), "map": self.map.currentText(),
                  "human": self.human.isChecked(), "human_team": self.human_team.currentIndex(),
                  "blue": [r.to_dict() for r in self.blue.rows], "orange": [r.to_dict() for r in self.orange.rows]}
        favs = [f for f in self.ctx.settings.favorites if f.get("name") != name] + [preset]
        self.ctx.settings.favorites = favs
        self.ctx.settings.save()
        self.status.setText(f"تم حفظ «{name}».")

    def load_preset(self) -> None:
        favs = self.ctx.settings.favorites
        if not favs:
            QMessageBox.information(self, "التشكيلات", "لا توجد تشكيلات محفوظة بعد.")
            return
        name, ok = QInputDialog.getItem(self, "تحميل تشكيلة", "اختر:", [f["name"] for f in favs], 0, False)
        if not ok:
            return
        p = next(f for f in favs if f["name"] == name)
        self.size.setValue(p["size"])
        self.map.setCurrentText(p["map"])
        self.human.setChecked(p["human"])
        self.human_team.setCurrentIndex(p["human_team"])
        for rows, data in ((self.blue.rows, p["blue"]), (self.orange.rows, p["orange"])):
            for r, d in zip(rows, data):
                r.load(d)


__all__ = ["PlayPage", "rank_index"]
