from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
    QWidget,
)

from ...core import multiplayer as mp
from ...core.match import MAPS
from ..common import card, header, run_bg

NOTE = ("الجلسات تعمل عبر بنية RLBot v5 الحالية: سيرفرات RocketHost (البوتات تعمل على السيرفر، فلا يحتاج "
        "أي لاعب لتنزيلها) وقائمة RLLobby. للكمبيوتر فقط؛ لاعبو الكونسول لا يمكنهم دخول مباريات RLBot.")


class MultiplayerPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.servers: list[mp.RHostServer] = []
        self.lobbies: list[mp.Lobby] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(header("Multiplayer", NOTE))
        tabs = QTabWidget()
        tabs.addTab(self._browser(), "الجلسات")
        tabs.addTab(self._host(), "Host")
        tabs.addTab(self._join(), "Join")
        root.addWidget(tabs, 1)
        self.status = QLabel()
        self.status.setObjectName("muted")
        root.addWidget(self.status)
        self.refresh()

    # Session browser
    def _browser(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("ابحث باسم الجلسة…")
        self.region_filter = QComboBox()
        self.region_filter.addItem("كل المناطق", "")
        for code, name in mp.REGIONS.items():
            self.region_filter.addItem(name, code)
        self.min_players = QSpinBox()
        self.min_players.setPrefix("لاعبون ≥ ")
        refresh = QPushButton("تحديث")
        for x in (self.search, self.region_filter, self.min_players, refresh):
            bar.addWidget(x)
        lay.addLayout(bar)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["الاسم", "المنطقة", "الخريطة", "اللاعبون", "كلمة مرور", "العنوان", "آخر تحديث"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)
        join = QPushButton("انضم للجلسة المحددة")
        join.setObjectName("primary")
        lay.addWidget(join)
        refresh.clicked.connect(self.refresh)
        self.search.textChanged.connect(self.render_lobbies)
        self.region_filter.currentIndexChanged.connect(self.render_lobbies)
        self.min_players.valueChanged.connect(self.render_lobbies)
        join.clicked.connect(self.join_selected)
        self.table.doubleClicked.connect(self.join_selected)
        return w

    def _host(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()
        self.h_name = QLineEdit()
        self.h_name.setPlaceholderText("مثال: Kuwait Diamond 2v2")
        self.h_pass = QLineEdit()
        self.h_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.h_region = QComboBox()
        self.h_server = QComboBox()
        self.h_map = QComboBox()
        self.h_map.addItems(list(MAPS))
        self.h_blue = QLineEdit()
        self.h_blue.setPlaceholderText("أسماء بوتات RocketHost مفصولة بفواصل")
        self.h_orange = QLineEdit()
        self.h_orange.setPlaceholderText("مثال: nexto,nexto")
        self.h_bots = QLabel()
        self.h_bots.setWordWrap(True)
        self.h_bots.setObjectName("muted")
        for lbl, x in [("اسم الجلسة", self.h_name), ("كلمة المرور", self.h_pass), ("المنطقة", self.h_region),
                       ("السيرفر", self.h_server), ("الملعب", self.h_map), ("بوتات الأزرق", self.h_blue),
                       ("بوتات البرتقالي", self.h_orange), ("البوتات المتاحة", self.h_bots)]:
            form.addRow(lbl, x)
        c = card(title="استضافة جلسة على RocketHost")
        c.layout().addLayout(form)
        lay.addWidget(c)
        warn = QLabel("ملاحظة: سيرفرات RocketHost الحالية تحدد اسم الجلسة بنفسها وتبدأ بدون كلمة مرور؛ "
                      "يُرسل الاسم وكلمة المرور تلقائياً لأي سيرفر يدعمهما.")
        warn.setWordWrap(True)
        warn.setObjectName("muted")
        lay.addWidget(warn)
        go = QPushButton("Host")
        go.setObjectName("primary")
        lay.addWidget(go)
        lay.addStretch()
        self.h_region.currentIndexChanged.connect(self._fill_servers)
        self.h_server.currentIndexChanged.connect(self._load_server_bots)
        go.clicked.connect(self.host)
        return w

    def _join(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()
        self.j_name = QLineEdit()
        self.j_name.setPlaceholderText("اسم الجلسة أو IP:Port")
        self.j_pass = QLineEdit()
        self.j_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("اسم الجلسة", self.j_name)
        form.addRow("كلمة المرور", self.j_pass)
        c = card(title="الانضمام لجلسة")
        c.layout().addLayout(form)
        go = QPushButton("Join")
        go.setObjectName("primary")
        c.layout().addWidget(go)
        lay.addWidget(c)
        lay.addStretch()
        go.clicked.connect(self.join_by_name)
        return w

    # Data
    def refresh(self):
        self.status.setText("جارٍ تحميل الجلسات والسيرفرات…")
        run_bg(mp.fetch_lobbies, on_done=self._lobbies_loaded, on_error=lambda m: self.status.setText(f"RLLobby: {m}"))
        run_bg(mp.fetch_servers, on_done=self._servers_loaded, on_error=lambda m: self.status.setText(f"RocketHost: {m}"))

    def _lobbies_loaded(self, lobbies):
        self.lobbies = mp.sort_by_region_priority(lobbies, self.ctx.settings.preferred_region)
        self.render_lobbies()
        self.status.setText(f"{len(lobbies)} جلسة · {len(self.servers)} سيرفر RocketHost")

    def _servers_loaded(self, servers):
        self.servers = mp.sort_by_region_priority(servers, self.ctx.settings.preferred_region)
        self.h_region.blockSignals(True)
        self.h_region.clear()
        pref = self.ctx.settings.preferred_region
        for code in [pref] + [c for c in mp.REGIONS if c != pref]:
            n = sum(1 for s in self.servers if s.region == code)
            self.h_region.addItem(f"{mp.REGIONS[code]} — {n} سيرفر" if n else f"{mp.REGIONS[code]} — غير متاح حالياً", code)
        first = next((i for i in range(self.h_region.count())
                      if any(s.region == self.h_region.itemData(i) for s in self.servers)), 0)
        self.h_region.setCurrentIndex(first)
        self.h_region.blockSignals(False)
        self._fill_servers()
        self.status.setText(f"{len(self.lobbies)} جلسة · {len(servers)} سيرفر RocketHost")

    def _fill_servers(self):
        code = self.h_region.currentData()
        self.h_server.clear()
        for s in self.servers:
            if s.region == code:
                self.h_server.addItem(f"{s.location} ({s.address})", s)

    def _load_server_bots(self):
        s = self.h_server.currentData()
        if not s:
            self.h_bots.setText("—")
            return
        run_bg(mp.fetch_server_bots, s,
               on_done=lambda bots: self.h_bots.setText(", ".join(b.get("name", "") for b in bots) or "—"),
               on_error=lambda m: self.h_bots.setText(m))

    def render_lobbies(self, *_):
        q = self.search.text().lower()
        reg = self.region_filter.currentData()
        rows = [lb for lb in self.lobbies if (not q or q in lb.name.lower()) and (not reg or lb.region == reg)
                and lb.player_count >= self.min_players.value()]
        self.table.setRowCount(len(rows))
        for i, lb in enumerate(rows):
            vals = [lb.name, mp.REGIONS.get(lb.region, "?"), lb.map, str(lb.player_count),
                    "نعم" if lb.has_password else "لا", lb.address, f"{lb.seconds_since_update}s"]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 0:
                    it.setData(256, lb)
                self.table.setItem(i, j, it)

    # Actions
    def _send(self, cmd: str, ok_msg: str):
        self.status.setText("جارٍ الاتصال…")
        run_bg(self.ctx.runner.console, cmd, on_done=lambda _: self.status.setText(ok_msg),
               on_error=lambda m: QMessageBox.critical(self, "Multiplayer", m))

    def join_selected(self, *_):
        row = self.table.currentRow()
        if row < 0:
            return
        lb: mp.Lobby = self.table.item(row, 0).data(256)
        pw = ""
        if lb.has_password:
            from PySide6.QtWidgets import QInputDialog
            pw, ok = QInputDialog.getText(self, lb.name, "كلمة المرور:", QLineEdit.EchoMode.Password)
            if not ok:
                return
        self._send(mp.join_command(lb.address, pw), f"تم إرسال أمر الانضمام إلى {lb.name}.")

    def join_by_name(self):
        name = self.j_name.text().strip()
        if not name:
            return
        if ":" in name and name.replace(".", "").replace(":", "").isdigit():
            address = name
        else:
            lb = mp.find_lobby(self.lobbies, name)
            if lb is None:
                QMessageBox.warning(self, "Join", "لم يتم العثور على جلسة بهذا الاسم. حدّث القائمة أو أدخل IP:Port.")
                return
            address = lb.address
        self._send(mp.join_command(address, self.j_pass.text()), f"تم إرسال أمر الانضمام إلى {name}.")

    def host(self):
        s = self.h_server.currentData()
        if not s:
            QMessageBox.warning(self, "Host", "لا يوجد سيرفر RocketHost في هذه المنطقة حالياً.")
            return
        split = lambda t: [x.strip() for x in t.split(",") if x.strip()]  # noqa: E731
        req = mp.HostRequest(server=s, map_upk=MAPS[self.h_map.currentText()], blue_bots=split(self.h_blue.text()),
                             orange_bots=split(self.h_orange.text()), session_name=self.h_name.text().strip(),
                             password=self.h_pass.text())
        self.status.setText("RocketHost يجهّز المباراة…")

        def job():
            msg = mp.request_host(req)
            self.ctx.runner.console(mp.host_start_command(msg, req.password))
            return msg

        run_bg(job, on_done=lambda m: self.status.setText(f"الجلسة جاهزة: {m}"),
               on_error=lambda m: QMessageBox.critical(self, "Host", m))
