from PySide6.QtWidgets import (
    QComboBox, QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)
from PySide6.QtGui import QColor

from ...core.match import MAPS, MatchSpec, Slot, psyonix_for_rank
from ...core.ranks import GROUP_COLORS, RANKS, group_of
from ...core.training import Ladder, estimate_player_rank
from ..common import card, header, run_bg


class TrainingPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.ladder = Ladder()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        root.addWidget(header("Training", "سلم تدريبي من Bronze 1 إلى SSL. فوزان متتاليان يرفعان الصعوبة، وخسارتان تخفضانها."))

        cfg = QWidget()
        g = QGridLayout(cfg)
        g.setContentsMargins(0, 0, 0, 0)
        self.start_rank = QComboBox()
        self.start_rank.addItems(RANKS)
        self.end_rank = QComboBox()
        self.end_rank.addItems(RANKS)
        self.end_rank.setCurrentIndex(len(RANKS) - 1)
        self.style = QComboBox()
        self.style.addItem("الكل", "")
        self.style.addItem("Mechanical", "Mechanical")
        self.style.addItem("Non-Mechanical", "Non-Mechanical")
        self.size = QSpinBox()
        self.size.setRange(1, 3)
        self.size.setSuffix(" ضد ")
        self.map = QComboBox()
        self.map.addItems(list(MAPS))
        for i, (lbl, w) in enumerate([("من رتبة", self.start_rank), ("إلى رتبة", self.end_rank),
                                      ("نوع البوت", self.style), ("الطور", self.size), ("الملعب", self.map)]):
            g.addWidget(QLabel(lbl), 0, i)
            g.addWidget(w, 1, i)
        new = QPushButton("إنشاء سلم جديد")
        g.addWidget(new, 1, 5)
        root.addWidget(card(cfg, title="إعداد التدريب"))

        mid = QHBoxLayout()
        self.steps = QListWidget()
        mid.addWidget(card(self.steps, title="السلم"), 1)

        right = QWidget()
        r = QVBoxLayout(right)
        r.setContentsMargins(0, 0, 0, 0)
        self.current = QLabel()
        self.current.setStyleSheet("font-size:20px; font-weight:700;")
        self.opponent = QComboBox()
        self.estimate = QLabel()
        self.estimate.setObjectName("muted")
        diff = QHBoxLayout()
        down = QPushButton("− خفض الصعوبة")
        up = QPushButton("+ رفع الصعوبة")
        diff.addWidget(down)
        diff.addWidget(up)
        play = QPushButton("ابدأ مباراة التدريب")
        play.setObjectName("primary")
        res = QHBoxLayout()
        self.gf = QSpinBox()
        self.ga = QSpinBox()
        rec = QPushButton("سجّل النتيجة")
        res.addWidget(QLabel("أهدافي"))
        res.addWidget(self.gf)
        res.addWidget(QLabel("أهداف البوت"))
        res.addWidget(self.ga)
        res.addWidget(rec)
        for w in (self.current, QLabel("الخصم:"), self.opponent):
            r.addWidget(w)
        r.addLayout(diff)
        r.addWidget(play)
        r.addLayout(res)
        r.addWidget(self.estimate)
        r.addStretch()
        mid.addWidget(card(right, title="المرحلة الحالية"), 1)
        root.addLayout(mid, 1)

        new.clicked.connect(self.new_ladder)
        up.clicked.connect(lambda: (self.ladder.raise_difficulty(), self.refresh()))
        down.clicked.connect(lambda: (self.ladder.lower_difficulty(), self.refresh()))
        play.clicked.connect(self.play)
        rec.clicked.connect(self.record)
        self.style.currentIndexChanged.connect(self.refresh)
        ctx.bus.catalog_changed.connect(self.refresh)
        self.new_ladder()

    def new_ladder(self):
        lo, hi = sorted((self.start_rank.currentIndex(), self.end_rank.currentIndex()))
        self.ladder = Ladder(start=lo, end=hi, current=lo)
        self.refresh()

    def _opponents(self, idx: int):
        return [e for e in self.ctx.catalog.for_rank(idx, self.style.currentData() or None)]

    def refresh(self, *_):
        self.steps.clear()
        for i in range(self.ladder.start, self.ladder.end + 1):
            ops = self._opponents(i)
            mark = "▶ " if i == self.ladder.current else ("✓ " if i < self.ladder.current else "  ")
            item = QListWidgetItem(f"{mark}{RANKS[i]}  —  {ops[0].name if ops else 'Psyonix ' + psyonix_for_rank(i)}")
            item.setForeground(QColor(GROUP_COLORS[group_of(i)]))
            self.steps.addItem(item)
        self.steps.setCurrentRow(self.ladder.current - self.ladder.start)
        idx = self.ladder.current
        self.current.setText(RANKS[idx])
        self.current.setStyleSheet(f"font-size:20px; font-weight:700; color:{GROUP_COLORS[group_of(idx)]};")
        self.opponent.clear()
        for e in self._opponents(idx):
            self.opponent.addItem(e.name if e.installed else f"{e.name} (غير مثبت)", e.name)
        self.opponent.addItem(f"Psyonix {psyonix_for_rank(idx)}", "__psyonix__")
        if self.ladder.history:
            self.estimate.setText(f"مستواك التقريبي: {estimate_player_rank(self.ladder.history)} "
                                  f"(من {len(self.ladder.history)} مباراة)")
        else:
            self.estimate.setText("سجّل نتائج مبارياتك ليظهر تقدير مستواك.")

    def play(self):
        n = self.size.value()
        idx = self.ladder.current
        choice = self.opponent.currentData()
        slots = [Slot("human", 0)]
        for _ in range(n - 1):
            slots.append(self._bot_slot(choice, 0, idx))
        for _ in range(n):
            slots.append(self._bot_slot(choice, 1, idx))
        spec = MatchSpec(slots=slots, map_name=self.map.currentText(), launcher=self.ctx.settings.launcher)
        errors = spec.validate()
        if errors:
            QMessageBox.warning(self, "التدريب", "\n".join(errors))
            return
        run_bg(self.ctx.runner.start, spec, on_error=lambda m: QMessageBox.critical(self, "فشل", m))

    def _bot_slot(self, choice, team, idx) -> Slot:
        if choice == "__psyonix__":
            s = psyonix_for_rank(idx)
            return Slot("psyonix", team, f"Psyonix {s}", psyonix_skill=s)
        e = self.ctx.catalog.find(choice)
        return Slot("bot", team, e.name, toml_path=e.toml_path)

    def record(self):
        self.ladder.record(self.gf.value(), self.ga.value())
        self.ctx.settings.player_rating = None
        self.refresh()
