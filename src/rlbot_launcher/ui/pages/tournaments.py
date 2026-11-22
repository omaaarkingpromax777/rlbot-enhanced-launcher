import json
import random

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from ...core.challenge import RankChallenge
from ...core.match import MAPS, MatchSpec, Slot, psyonix_for_rank
from ...core.ranks import GROUP_COLORS, GROUPS, RANKS, group_of
from ...core.settings import DATA_DIR
from ...core.tournament import HUMAN_ID, Tournament, TournamentStore, round_name
from ..common import card, header, run_bg
from ..theme import ACCENT, BORDER, MUTED, PANEL_2

CATS = {"": "الجميع", "Mechanical": "Mechanical فقط", "Non-Mechanical": "Non-Mechanical فقط"}
CHALLENGE_FILE = DATA_DIR / "rank_challenge.json"


def _color(p) -> str:
    if p.kind == "human":
        return ACCENT
    return GROUP_COLORS.get(group_of(p.rank_idx), MUTED) if p.rank_idx >= 0 else MUTED


class MatchCard(QFrame):
    def __init__(self, t: Tournament, m, current: bool):
        super().__init__()
        self.setObjectName("card")
        border = ACCENT if current else BORDER
        self.setStyleSheet(f"QFrame#card {{ border: 1px solid {border}; border-radius: 10px; background: {PANEL_2}; }}")
        self.setFixedWidth(250)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)
        for pid, score in ((m.a, m.score_a), (m.b, m.score_b)):
            row = QHBoxLayout()
            if pid is None:
                name = QLabel("—" if m.round == 0 else "بانتظار الفائز")
                name.setObjectName("muted")
                row.addWidget(name, 1)
            else:
                p = t.participants[pid]
                won = m.winner == pid and not m.is_bye
                name = QLabel(f"{p.seed}. {p.name}")
                name.setStyleSheet(f"font-weight:{'700' if won else '400'}; color:{'#fff' if won or not m.winner else MUTED};")
                rank = QLabel(RANKS[p.rank_idx] if p.rank_idx >= 0 else "لاعب")
                rank.setStyleSheet(f"color:{_color(p)}; font-size:11px;")
                row.addWidget(name, 1)
                row.addWidget(rank)
            sc = QLabel("" if score is None else str(score))
            sc.setStyleSheet("font-weight:700; min-width:18px;")
            row.addWidget(sc)
            lay.addLayout(row)
        if m.simulated:
            s = QLabel("نتيجة محاكاة")
            s.setObjectName("muted")
            s.setStyleSheet("font-size:10px;")
            lay.addWidget(s)
        if m.is_bye:
            s = QLabel("تأهل مباشر (bye)")
            s.setObjectName("muted")
            lay.addWidget(s)


class TournamentsPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.store = TournamentStore(DATA_DIR / "tournaments")
        self.t: Tournament | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(header("Tournaments", "بطولات إقصائية بين البوتات، ويمكنك المشاركة فيها كلاعب. تُحفظ كل البطولات ونتائجها."))
        self.tabs = QTabWidget()
        self.tabs.addTab(self._new_tab(), "بطولة جديدة")
        self.tabs.addTab(self._bracket_tab(), "Bracket")
        self.tabs.addTab(self._stats_tab(), "النتائج والإحصائيات")
        self.tabs.addTab(self._history_tab(), "سجل البطولات")
        self.tabs.addTab(self._challenge_tab(), "Rank Challenge")
        root.addWidget(self.tabs, 1)
        self.load_history()
        self.load_challenge()

    # New tournament
    def _new_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.n_name = QLineEdit("بطولتي")
        groups = QWidget()
        g = QGridLayout(groups)
        g.setContentsMargins(0, 0, 0, 0)
        self.group_boxes: dict[str, QCheckBox] = {}
        for i, grp in enumerate(GROUPS):
            cb = QCheckBox(grp)
            cb.setStyleSheet(f"color:{GROUP_COLORS[grp]}; font-weight:600;")
            cb.setChecked(grp == "Diamond")
            self.group_boxes[grp] = cb
            g.addWidget(cb, i // 4, i % 4)
        presets = QHBoxLayout()
        for label, sel in [("Bronze فقط", ["Bronze"]), ("Bronze + Silver", ["Bronze", "Silver"]),
                           ("Diamond فقط", ["Diamond"]), ("Champion → GC", ["Champion", "Grand Champion"]),
                           ("الكل", GROUPS)]:
            b = QPushButton(label)
            b.setObjectName("chip")
            b.clicked.connect(lambda _=False, s=sel: [cb.setChecked(k in s) for k, cb in self.group_boxes.items()])
            presets.addWidget(b)
        presets.addStretch()
        self.n_size = QComboBox()
        for n in (4, 8, 16, 32):
            self.n_size.addItem(f"{n} مشاركين", n)
        self.n_size.setCurrentIndex(1)
        self.n_cat = QComboBox()
        for k, v in CATS.items():
            self.n_cat.addItem(v, k)
        self.n_mode = QComboBox()
        for n in (1, 2, 3):
            self.n_mode.addItem(f"{n}v{n}", n)
        self.n_map = QComboBox()
        self.n_map.addItems(list(MAPS))
        self.n_human = QCheckBox("أشارك أنا كلاعب في البطولة")
        self.n_installed = QCheckBox("البوتات المثبتة فقط")
        form = QFormLayout()
        form.addRow("الاسم", self.n_name)
        form.addRow("الرتب المشاركة", groups)
        form.addRow("", presets)
        form.addRow("عدد المشاركين", self.n_size)
        form.addRow("نوع البوتات", self.n_cat)
        form.addRow("الطور", self.n_mode)
        form.addRow("الملعب", self.n_map)
        form.addRow("", self.n_human)
        form.addRow("", self.n_installed)
        c = card(title="إعداد البطولة")
        c.layout().addLayout(form)
        lay.addWidget(c)
        create = QPushButton("إنشاء البطولة")
        create.setObjectName("primary")
        create.clicked.connect(self.create)
        lay.addWidget(create)
        lay.addStretch()
        return w

    def create(self):
        groups = [g for g, cb in self.group_boxes.items() if cb.isChecked()]
        if not groups:
            QMessageBox.warning(self, "البطولة", "اختر رتبة واحدة على الأقل.")
            return
        t = Tournament.create(self.ctx.catalog, name=self.n_name.text().strip() or "بطولة", groups=groups,
                              size=self.n_size.currentData(), category=self.n_cat.currentData(),
                              include_human=self.n_human.isChecked(), team_size=self.n_mode.currentData(),
                              map_name=self.n_map.currentText(), installed_only=self.n_installed.isChecked())
        self.open_tournament(t)
        self.store.save(t)
        self.load_history()
        n_psy = sum(p.kind == "psyonix" for p in t.participants.values())
        if n_psy:
            self.ctx.bus.status.emit(f"لا توجد بوتات كافية في الرتب المختارة؛ أُكملت البطولة بـ {n_psy} بوت Psyonix.")

    def open_tournament(self, t: Tournament):
        self.t = t
        self.render_bracket()
        self.render_stats()
        self.tabs.setCurrentIndex(1)

    # Bracket
    def _bracket_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        top = QHBoxLayout()
        self.b_title = QLabel("لا توجد بطولة مفتوحة.")
        self.b_title.setStyleSheet("font-size:16px; font-weight:700;")
        top.addWidget(self.b_title, 1)
        self.b_next = QLabel()
        self.b_next.setObjectName("muted")
        top.addWidget(self.b_next)
        lay.addLayout(top)
        self.b_area = QScrollArea()
        self.b_area.setWidgetResizable(True)
        lay.addWidget(self.b_area, 1)
        actions = QHBoxLayout()
        self.b_champion = QLabel()
        self.b_champion.setStyleSheet("font-size:16px; font-weight:700; color:#e2b43b;")
        self.b_play = QPushButton("العب المباراة التالية")
        self.b_play.setObjectName("primary")
        self.b_manual = QPushButton("إدخال النتيجة يدوياً")
        self.b_sim = QPushButton("محاكاة سريعة")
        self.b_sim.setToolTip("نتيجة تقديرية من قوة الرتبة، وتُعلَّم كمحاكاة وليست مباراة حقيقية.")
        self.b_sim_all = QPushButton("محاكاة كل مباريات البوتات")
        for x in (self.b_champion,):
            actions.addWidget(x, 1)
        for x in (self.b_sim_all, self.b_sim, self.b_manual, self.b_play):
            actions.addWidget(x)
        lay.addLayout(actions)
        self.b_play.clicked.connect(self.play_next)
        self.b_manual.clicked.connect(self.manual_next)
        self.b_sim.clicked.connect(self.sim_next)
        self.b_sim_all.clicked.connect(self.sim_bots)
        return w

    def render_bracket(self):
        t = self.t
        inner = QWidget()
        inner.setObjectName("bracketInner")
        row = QHBoxLayout(inner)
        row.setAlignment(Qt.AlignmentFlag.AlignTop)
        nxt = t.next_match() if t else None
        if t:
            total = len(t.rounds)
            for r, matches in enumerate(t.rounds):
                col = QVBoxLayout()
                lbl = QLabel(round_name(r, total))
                lbl.setStyleSheet("font-weight:700; color:#8b93a7;")
                col.addWidget(lbl)
                col.addStretch()
                for m in matches:
                    col.addWidget(MatchCard(t, m, nxt is not None and m.id == nxt.id))
                    col.addStretch()
                row.addLayout(col)
            self.b_title.setText(f"{t.name} · {' + '.join(t.groups)} · {CATS[t.category]} · {t.team_size}v{t.team_size}")
            champ = t.participants[t.champion].name if t.champion else None
            self.b_champion.setText(f"🏆 البطل: {champ}" if champ else "")
            if nxt:
                a, b = t.participants[nxt.a], t.participants[nxt.b]
                self.b_next.setText(f"التالي ({round_name(nxt.round, total)}): {a.name} ضد {b.name}")
            else:
                self.b_next.setText("انتهت البطولة." if champ else "")
        for btn in (self.b_play, self.b_manual, self.b_sim, self.b_sim_all):
            btn.setEnabled(nxt is not None)
        if nxt is not None:
            self.b_sim.setEnabled(HUMAN_ID not in (nxt.a, nxt.b))
        self.b_area.setWidget(inner)

    def _after_result(self):
        self.store.save(self.t)
        self.render_bracket()
        self.render_stats()
        self.load_history()

    def play_next(self):
        m = self.t.next_match()
        spec = self.t.spec_for(m)
        errors = spec.validate()
        if errors:
            QMessageBox.warning(self, "المباراة", "\n".join(errors) + "\n\nثبّت البوتات من قسم Bots أو أدخل النتيجة يدوياً.")
            return
        self.b_play.setEnabled(False)
        self.ctx.bus.status.emit("المباراة تعمل… ستُسجَّل النتيجة تلقائياً عند نهايتها.")

        def done(scores):
            a, b = scores
            if a == b:
                QMessageBox.information(self, "تعادل", "انتهت بالتعادل؛ أدخل نتيجة الوقت الإضافي يدوياً.")
                self.render_bracket()
                return
            self.t.record(m.id, a, b)
            self._after_result()

        run_bg(self.ctx.runner.play_to_end, spec, on_done=done,
               on_error=lambda e: (QMessageBox.critical(self, "فشل", e), self.render_bracket()))

    def manual_next(self):
        m = self.t.next_match()
        a, b = self.t.participants[m.a].name, self.t.participants[m.b].name
        text, ok = QInputDialog.getText(self, "النتيجة", f"{a} - {b}  (مثال: 3-1):")
        if not ok:
            return
        try:
            sa, sb = (int(x) for x in text.replace(":", "-").split("-"))
            self.t.record(m.id, sa, sb)
        except ValueError as e:
            QMessageBox.warning(self, "النتيجة", str(e) or "صيغة غير صحيحة")
            return
        self._after_result()

    def sim_next(self):
        self.t.simulate(self.t.next_match())
        self._after_result()

    def sim_bots(self):
        rng = random.Random()
        while (m := self.t.next_match()) is not None and HUMAN_ID not in (m.a, m.b):
            self.t.simulate(m, rng)
        # Also resolve bot-only matches elsewhere in the same round while the human match waits.
        for rnd in self.t.rounds:
            for m in rnd:
                if m.ready and HUMAN_ID not in (m.a, m.b):
                    self.t.simulate(m, rng)
        self._after_result()

    # Stats
    def _stats_tab(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        self.s_table = QTableWidget(0, 9)
        self.s_table.setHorizontalHeaderLabels(["#", "الاسم", "الرتبة", "النوع", "الفئة", "فوز-خسارة", "نسبة الفوز", "الأهداف", "الحالة"])
        self.s_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.s_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.s_table.verticalHeader().hide()
        self.s_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.s_table.horizontalHeader().setStretchLastSection(True)
        self.s_log = QListWidget()
        self.s_log.setMinimumWidth(280)
        lay.addWidget(self.s_table, 3)
        lay.addWidget(card(self.s_log, title="سجل المباريات"), 1)
        self.s_table.currentCellChanged.connect(lambda r, *_: self.show_log(r))
        self._stats = []
        return w

    def render_stats(self):
        self._stats = self.t.stats() if self.t else []
        self.s_table.setRowCount(len(self._stats))
        for i, r in enumerate(self._stats):
            p = r["participant"]
            status = "البطل" if self.t.champion == p.id else ("خرج" if r["eliminated"] else "مستمر")
            rank = f"{RANKS[p.rank_idx]}  ({p.rank})" if p.rank_idx >= 0 else "—"
            vals = [str(p.seed), p.name, rank, p.bot_type, p.category, f"{r['w']}-{r['l']}",
                    f"{r['win_pct']:.0%}", f"{r['gf']}:{r['ga']}", status]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 2:
                    it.setForeground(QColor(_color(p)))
                self.s_table.setItem(i, j, it)
        if self._stats:
            self.s_table.selectRow(0)
            self.show_log(0)

    def show_log(self, row: int):
        self.s_log.clear()
        if not (0 <= row < len(self._stats)):
            return
        for e in self._stats[row]["log"]:
            mark = "✓" if e["won"] else "✗"
            sim = " (محاكاة)" if e["simulated"] else ""
            it = QListWidgetItem(f"{mark} {e['round']}: ضد {e['opponent']}  {e['score']}{sim}")
            it.setForeground(QColor("#3ecf8e" if e["won"] else "#e5484d"))
            self.s_log.addItem(it)
        if not self._stats[row]["log"]:
            self.s_log.addItem("لم يلعب بعد.")

    # History
    def _history_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.h_list = QListWidget()
        lay.addWidget(self.h_list, 1)
        row = QHBoxLayout()
        open_btn = QPushButton("فتح")
        del_btn = QPushButton("حذف")
        row.addStretch()
        row.addWidget(del_btn)
        row.addWidget(open_btn)
        lay.addLayout(row)
        open_btn.clicked.connect(self.open_selected)
        self.h_list.itemDoubleClicked.connect(self.open_selected)
        del_btn.clicked.connect(self.delete_selected)
        return w

    def load_history(self):
        self.h_list.clear()
        self._history = self.store.list()
        for t in self._history:
            champ = t.participants[t.champion].name if t.champion else "جارية"
            self.h_list.addItem(f"{t.created.replace('T', ' ')}  ·  {t.name}  ·  {' + '.join(t.groups)}  ·  "
                                f"{len(t.participants)} مشارك  ·  البطل: {champ}")

    def open_selected(self, *_):
        i = self.h_list.currentRow()
        if 0 <= i < len(self._history):
            self.open_tournament(self._history[i])

    def delete_selected(self):
        i = self.h_list.currentRow()
        if 0 <= i < len(self._history):
            self.store.delete(self._history[i].id)
            self.load_history()

    # Rank challenge
    def _challenge_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        cfg = QHBoxLayout()
        self.c_start = QComboBox()
        self.c_start.addItems(GROUPS)
        self.c_start.setCurrentText("Diamond")
        self.c_target = QComboBox()
        self.c_target.addItems(GROUPS)
        self.c_target.setCurrentText("Supersonic Legend")
        self.c_n = QSpinBox()
        self.c_n.setRange(1, 10)
        self.c_n.setValue(5)
        self.c_ratio = QDoubleSpinBox()
        self.c_ratio.setRange(0.1, 1.0)
        self.c_ratio.setSingleStep(0.05)
        self.c_ratio.setValue(0.6)
        self.c_cat = QComboBox()
        for k, v in CATS.items():
            self.c_cat.addItem(v, k)
        start = QPushButton("ابدأ التحدي")
        for lbl, x in [("من", self.c_start), ("حتى", self.c_target), ("بوتات لكل رتبة", self.c_n),
                       ("نسبة الفوز المطلوبة", self.c_ratio), ("النوع", self.c_cat)]:
            cfg.addWidget(QLabel(lbl))
            cfg.addWidget(x)
        cfg.addWidget(start)
        c = card(title="Rank Challenge: تغلّب على نسبة من بوتات الرتبة لتنتقل للرتبة التالية")
        c.layout().addLayout(cfg)
        lay.addWidget(c)
        self.c_path = QHBoxLayout()
        lay.addLayout(self.c_path)
        body = QHBoxLayout()
        self.c_list = QListWidget()
        body.addWidget(card(self.c_list, title="خصوم الرتبة الحالية"), 1)
        right = QWidget()
        r = QVBoxLayout(right)
        self.c_status = QLabel()
        self.c_status.setStyleSheet("font-size:18px; font-weight:700;")
        self.c_progress = QLabel()
        self.c_progress.setObjectName("muted")
        play = QPushButton("العب ضد الخصم التالي")
        play.setObjectName("primary")
        manual = QPushButton("إدخال النتيجة يدوياً")
        for x in (self.c_status, self.c_progress, play, manual):
            r.addWidget(x)
        r.addStretch()
        body.addWidget(card(right, title="التقدم"), 1)
        lay.addLayout(body, 1)
        start.clicked.connect(self.start_challenge)
        play.clicked.connect(self.play_challenge)
        manual.clicked.connect(self.manual_challenge)
        self.ch: RankChallenge | None = None
        return w

    def start_challenge(self):
        lo, hi = GROUPS.index(self.c_start.currentText()), GROUPS.index(self.c_target.currentText())
        self.ch = RankChallenge(group=GROUPS[min(lo, hi)], target=GROUPS[max(lo, hi)], opponents_per_group=self.c_n.value(),
                                pass_ratio=self.c_ratio.value(), category=self.c_cat.currentData())
        self.ch.setup(self.ctx.catalog)
        self.save_challenge()
        self.render_challenge()

    def load_challenge(self):
        if CHALLENGE_FILE.exists():
            self.ch = RankChallenge.from_dict(json.loads(CHALLENGE_FILE.read_text("utf-8")))
        self.render_challenge()

    def save_challenge(self):
        CHALLENGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHALLENGE_FILE.write_text(json.dumps(self.ch.to_dict(), ensure_ascii=False, indent=1), "utf-8")

    def render_challenge(self):
        while self.c_path.count():
            it = self.c_path.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.c_list.clear()
        ch = self.ch
        if ch is None:
            self.c_status.setText("ابدأ تحدياً جديداً.")
            self.c_progress.setText("")
            return
        cur = GROUPS.index(ch.group)
        for i, g in enumerate(GROUPS[: GROUPS.index(ch.target) + 1]):
            done = i < cur or (ch.finished and i == cur)
            lbl = QLabel(("✓ " if done else "▶ " if i == cur else "") + g)
            fg = "#111" if g in ("Silver", "Gold", "Platinum", "Supersonic Legend") else "white"
            bg = GROUP_COLORS[g] if (done or i == cur) else "#2a3040"
            lbl.setStyleSheet(f"background:{bg}; color:{fg if bg != '#2a3040' else MUTED}; border-radius:10px; padding:4px 12px; font-weight:600;")
            self.c_path.addWidget(lbl)
        self.c_path.addStretch()
        played = {g.opponent: g for g in ch.current_games()}
        for name in ch.opponents:
            g = played.get(name)
            e = self.ctx.catalog.find(name)
            extra = f"  ·  ≈ {RANKS[e.band.mid]}  ({e.expected_level})" if e and e.band else ""
            if g:
                it = QListWidgetItem(f"{'✓' if g.won else '✗'} {name}  {g.goals_for}-{g.goals_against}{extra}")
                it.setForeground(QColor("#3ecf8e" if g.won else "#e5484d"))
            else:
                it = QListWidgetItem(f"• {name}{extra}" + ("" if e and e.installed else "  (غير مثبت)"))
            self.c_list.addItem(it)
        wins, played_n, total = ch.progress()
        if ch.finished:
            self.c_status.setText(f"🏆 أكملت التحدي حتى {ch.target}!")
        else:
            self.c_status.setText(f"الرتبة الحالية: {ch.group}")
            self.c_status.setStyleSheet(f"font-size:18px; font-weight:700; color:{GROUP_COLORS[ch.group]};")
        self.c_progress.setText(f"فوز {wins} من {played_n} · المطلوب {ch.needed_wins} من {total} للانتقال")

    def _challenge_result(self, opp: str, gf: int, ga: int):
        res = self.ch.record(opp, gf, ga, self.ctx.catalog)
        self.save_challenge()
        self.render_challenge()
        msg = {"promoted": f"ممتاز! انتقلت إلى {self.ch.group}.", "failed": "لم تحقق النسبة المطلوبة؛ أعد محاولة هذه الرتبة.",
               "champion": "أكملت التحدي!"}.get(res)
        if msg:
            QMessageBox.information(self, "Rank Challenge", msg)

    def play_challenge(self):
        if not self.ch or self.ch.finished:
            return
        opp = self.ch.next_opponent()
        e = self.ctx.catalog.find(opp) if opp else None
        if e is None or not e.installed:
            idx = RANKS.index(f"{self.ch.group} 2") if self.ch.group != GROUPS[-1] else len(RANKS) - 1
            if QMessageBox.question(self, "غير مثبت", f"{opp} غير مثبت. العب ضد Psyonix {psyonix_for_rank(idx)} بدلاً منه؟") != QMessageBox.StandardButton.Yes:
                return
            bot = Slot("psyonix", 1, f"Psyonix {psyonix_for_rank(idx)}", psyonix_skill=psyonix_for_rank(idx))
        else:
            bot = Slot("bot", 1, e.name, toml_path=e.toml_path)
        spec = MatchSpec(slots=[Slot("human", 0), bot], launcher=self.ctx.settings.launcher)
        run_bg(self.ctx.runner.play_to_end, spec, on_done=lambda s: self._challenge_result(opp, s[0], s[1]),
               on_error=lambda m: QMessageBox.critical(self, "فشل", m))

    def manual_challenge(self):
        if not self.ch or self.ch.finished:
            return
        opp = self.ch.next_opponent()
        text, ok = QInputDialog.getText(self, "النتيجة", f"أنت - {opp}  (مثال: 3-1):")
        if not ok:
            return
        try:
            gf, ga = (int(x) for x in text.replace(":", "-").split("-"))
        except ValueError:
            return
        self._challenge_result(opp, gf, ga)
