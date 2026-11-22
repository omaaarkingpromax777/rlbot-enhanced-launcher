from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QSplitter, QTableView, QTextBrowser,
    QVBoxLayout, QWidget,
)

from ...core import botpack
from ...core.catalog import SKILL_KEYS, BotEntry
from ...core.ranks import GROUP_COLORS, GROUPS
from ..common import header, run_bg

COLUMNS = ["الاسم", "الرتبة التقديرية", "الفئة", "النوع", "التقييم", "الأسلوب", "المصدر", "الحالة"]
SKILL_LABELS = {"defense": "الدفاع", "offense": "الهجوم", "positioning": "التمركز", "air_dribble": "Air Dribble",
                "flick": "Flick", "recovery": "Recovery", "rotation": "Rotation"}


class BotModel(QAbstractTableModel):
    def __init__(self, entries: list[BotEntry]):
        super().__init__()
        self.entries = entries

    def set_entries(self, entries):
        self.beginResetModel()
        self.entries = entries
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.entries)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def headerData(self, s, o, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and o == Qt.Orientation.Horizontal:
            return COLUMNS[s]

    def data(self, idx, role=Qt.ItemDataRole.DisplayRole):
        e = self.entries[idx.row()]
        c = idx.column()
        if role == Qt.ItemDataRole.DisplayRole:
            rating = f"{e.rating:.1f}" if e.rating is not None else f"{e.overall}/10"
            return [e.name, e.expected_level, e.category, e.bot_type, rating, e.style, e.source,
                    "مثبت" if e.installed else "غير مثبت"][c]
        if role == Qt.ItemDataRole.ForegroundRole:
            if c == 1:
                return QColor(GROUP_COLORS.get(e.rank_group, "#8b93a7"))
            if c == 7:
                return QColor("#3ecf8e" if e.installed else "#8b93a7")
        if role == Qt.ItemDataRole.UserRole:
            return e
        if role == Qt.ItemDataRole.UserRole + 1:  # sort key
            if c == 1:
                return e.band.mid if e.band else 99
            if c == 4:
                return e.rating if e.rating is not None else e.overall
            return str(self.data(idx))


class BotsPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)
        root.addWidget(header("Bots", "كل بوتات RLBot و RLGym المصنفة. التطبيق ينزّل حزمة البوتات الرسمية ويحدّثها تلقائياً."))

        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("ابحث بالاسم أو المطوّر أو الأسلوب…")
        bar.addWidget(self.search, 2)
        self.cat_group = QButtonGroup(self)
        for i, (label, val) in enumerate([("الكل", None), ("Mechanical", "Mechanical"), ("Non-Mechanical", "Non-Mechanical")]):
            b = QPushButton(label)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setProperty("val", val)
            self.cat_group.addButton(b)
            bar.addWidget(b)
        self.installed_only = QCheckBox("المثبتة فقط")
        self.show_unranked = QCheckBox("إظهار السكربتات/الميمي")
        bar.addWidget(self.installed_only)
        bar.addWidget(self.show_unranked)
        root.addLayout(bar)

        ranks = QHBoxLayout()
        self.rank_group = QButtonGroup(self)
        for i, g in enumerate(["الكل"] + GROUPS):
            b = QPushButton(g)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setProperty("val", None if i == 0 else g)
            if i:
                b.setStyleSheet(f"QPushButton#chip {{ border-color: {GROUP_COLORS[g]}; }}")
            self.rank_group.addButton(b)
            ranks.addWidget(b)
        ranks.addStretch()
        root.addLayout(ranks)

        self.model = BotModel([])
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole + 1)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.detail = QTextBrowser()
        self.detail.setMinimumWidth(300)
        split = QSplitter()
        split.addWidget(self.table)
        split.addWidget(self.detail)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        root.addWidget(split, 1)

        foot = QHBoxLayout()
        self.count = QLabel()
        self.count.setObjectName("muted")
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.update_btn = QPushButton("تنزيل / تحديث حزمة البوتات")
        self.update_btn.setObjectName("primary")
        imp = QPushButton("استيراد بوت أو حزمة…")
        foot.addWidget(self.count, 1)
        foot.addWidget(self.progress, 1)
        foot.addWidget(imp)
        foot.addWidget(self.update_btn)
        root.addLayout(foot)

        self.search.textChanged.connect(self.apply_filter)
        self.cat_group.buttonClicked.connect(self.apply_filter)
        self.rank_group.buttonClicked.connect(self.apply_filter)
        self.installed_only.toggled.connect(self.apply_filter)
        self.show_unranked.toggled.connect(self.apply_filter)
        self.table.selectionModel().currentRowChanged.connect(self.show_detail)
        self.update_btn.clicked.connect(self.update_botpack)
        imp.clicked.connect(self.import_bots)
        ctx.bus.catalog_changed.connect(self.apply_filter)
        self.apply_filter()

    def apply_filter(self, *_):
        entries = self.ctx.catalog.filter(
            text=self.search.text(),
            category=self.cat_group.checkedButton().property("val"),
            group=self.rank_group.checkedButton().property("val"),
            installed_only=self.installed_only.isChecked(),
            include_unranked=self.show_unranked.isChecked(),
        )
        self.model.set_entries(entries)
        n_inst = sum(1 for e in self.ctx.catalog.entries if e.installed)
        self.count.setText(f"{len(entries)} بوت معروض · {n_inst} مثبت · {len(self.ctx.catalog.entries)} في الفهرس")
        if entries:
            self.table.setCurrentIndex(self.proxy.index(0, 0))
            self.show_detail(self.proxy.index(0, 0))

    def show_detail(self, cur, _prev=None):
        if not cur.isValid():
            return
        e: BotEntry = self.proxy.data(cur, Qt.ItemDataRole.UserRole)
        color = GROUP_COLORS.get(e.rank_group, "#8b93a7")
        bars = "".join(
            f"<tr><td>{SKILL_LABELS[k]}</td><td width='60%'><div style='background:#2a3040;'>"
            f"<div style='background:{color}; width:{e.skills.get(k, 0) * 10}%;'>&nbsp;</div></div></td>"
            f"<td>{e.skills.get(k, 0)}</td></tr>"
            for k in SKILL_KEYS if k in e.skills
        )
        measured = f"{e.rating_games} مباراة معايرة" if e.rating_games else "تقدير أولي (غير مقاس بعد)"
        self.detail.setHtml(f"""
            <h2>{e.name}</h2>
            <p><span style='color:{color}; font-weight:bold'>{e.expected_level}</span> · {e.category}</p>
            <p><b>النوع:</b> {e.bot_type}<br><b>الأسلوب:</b> {e.style}<br><b>المصدر:</b> {e.source}<br>
            <b>المطوّر:</b> {e.developer or '—'}<br><b>اللغة:</b> {e.language or '—'}<br><b>الأطوار:</b> {e.modes or '—'}<br>
            <b>الثقة:</b> {e.confidence or '—'} · {measured}</p>
            <table width='100%'>{bars}</table>
            <p style='color:#8b93a7'>{e.description}</p>
            <p style='color:#8b93a7'>{e.toml_path or ''}</p>""")

    def check_updates(self):
        s = self.ctx.settings

        def found(res):
            stale, rel = res
            if stale:
                self.update_btn.setText(f"تحديث متاح: {rel.tag} ({rel.size >> 20} MB)")
                self.ctx.bus.status.emit(f"إصدار جديد من حزمة البوتات متاح: {rel.tag}")

        run_bg(botpack.needs_update, s.botpack_tag, s.botpack_repo, on_done=found,
               on_error=lambda m: self.ctx.bus.status.emit(f"تعذر فحص التحديثات: {m}"))

    def update_botpack(self):
        s = self.ctx.settings
        self.update_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)

        def job(report):
            stale, rel = botpack.needs_update(s.botpack_tag, s.botpack_repo)
            if not stale and Path(s.botpack_dir).exists():
                return None
            botpack.download_and_extract(rel, Path(s.botpack_dir), report)
            return rel.tag

        def report(done, total):
            task.signals.progress.emit(done, total)

        task = run_bg(job, report, on_done=self._updated, on_error=self._update_failed)
        task.signals.progress.connect(self._progress)

    def _progress(self, done, total):
        if total:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(done * 100 / total))
            self.ctx.bus.status.emit(f"تنزيل حزمة البوتات: {done >> 20} / {total >> 20} MB")

    def _updated(self, tag):
        self.update_btn.setEnabled(True)
        self.progress.setVisible(False)
        if tag:
            self.ctx.settings.botpack_tag = tag
            self.ctx.settings.save()
        self.ctx.refresh_installed()
        self.ctx.bus.status.emit(f"حزمة البوتات محدثة ({self.ctx.settings.botpack_tag or 'محلي'}).")

    def _update_failed(self, msg):
        self.update_btn.setEnabled(True)
        self.progress.setVisible(False)
        QMessageBox.critical(self, "فشل التحديث", msg)

    def import_bots(self):
        d = QFileDialog.getExistingDirectory(self, "اختر مجلد بوت (يحتوي bot.toml) أو حزمة بوتات")
        if not d:
            return
        found = botpack.scan_bots(Path(d))
        if not found:
            QMessageBox.warning(self, "استيراد", "لم يتم العثور على أي bot.toml متوافق مع RLBot v5.")
            return
        self.ctx.catalog.attach_installed(found)
        self.ctx.bus.catalog_changed.emit()
        QMessageBox.information(self, "استيراد", f"تمت إضافة {len(found)} بوت.")
