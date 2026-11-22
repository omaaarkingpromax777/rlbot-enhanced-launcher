from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..core.ranks import GROUP_COLORS


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)


class Task(QRunnable):
    """Run fn in the global thread pool; callbacks are delivered on the UI thread."""

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = _Signals()

    def run(self):
        try:
            self.signals.done.emit(self.fn(*self.args, **self.kwargs))
        except Exception as e:  # noqa: BLE001 - surfaced to the user
            self.signals.failed.emit(str(e) or type(e).__name__)


_RUNNING: set[Task] = set()


def run_bg(fn: Callable, *args, on_done=None, on_error=None, **kwargs) -> Task:
    t = Task(fn, *args, **kwargs)
    t.setAutoDelete(False)
    _RUNNING.add(t)
    t.signals.done.connect(lambda _=None: _RUNNING.discard(t))
    t.signals.failed.connect(lambda _=None: _RUNNING.discard(t))
    if on_done:
        t.signals.done.connect(on_done)
    if on_error:
        t.signals.failed.connect(on_error)
    QThreadPool.globalInstance().start(t)
    return t


def card(*widgets: QWidget, title: str | None = None, horizontal: bool = False) -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    lay = QHBoxLayout(f) if horizontal else QVBoxLayout(f)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(10)
    if title:
        t = QLabel(title)
        t.setStyleSheet("font-weight:600; font-size:14px;")
        lay.addWidget(t)
    for w in widgets:
        lay.addWidget(w)
    return f


def header(title: str, subtitle: str = "") -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 6)
    h = QLabel(title)
    h.setObjectName("h1")
    lay.addWidget(h)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("muted")
        s.setWordWrap(True)
        lay.addWidget(s)
    return w


def rank_badge(group: str, text: str | None = None) -> QLabel:
    color = GROUP_COLORS.get(group, "#555")
    lbl = QLabel(text or group)
    fg = "#111" if group in ("Supersonic Legend", "Silver", "Gold", "Platinum") else "white"
    lbl.setStyleSheet(f"background:{color}; color:{fg}; border-radius:9px; padding:2px 10px; font-weight:600; font-size:11px;")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl
