# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in TESHIS: frameless pencerenin TEK yonlu fiziksel resize olcumu.

Neden tek yon / tek surec
-------------------------
`QWindow.startSystemResize()` Windows'un NATIVE MODAL resize dongusunu
baslatir. Fiziksel girdiyi Qt GUI thread'inden `processEvents()` dongusuyle
gondermek reentrancy uretir: press'ler gecikir, yanlis koordinatta gelir ve
60-90 px hareket 400-900 px geometri degisimi gibi anlamsiz sonuclar cikar.

Bu child bu yuzden:
- her calistirmada YALNIZ bir yon olcer (`--direction left`),
- Qt ana thread'i normal `APP.exec()` calistirir,
- fiziksel `SendInput` dizisini Qt'ye HIC dokunmayan ayri bir worker
  thread gonderir,
- sonuc, worker bitip native donusu oturduktan SONRA QTimer ile okunur.

Urun kodu DEGISTIRILMEZ; `FramelessResizeFilter` yalnizca saydam sayaclarla
sarilir ve tur sonunda geri yuklenir.

    MLC_NATIVE_SMOKE=1 MLC_NATIVE_TEST_VIDEO=<mkv> \\
        python tests/native_resize_diag_child.py --direction bottom
"""
import argparse
import ctypes
import os
import sys
import threading
import time
from ctypes import wintypes

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]
os.environ.pop("QT_QPA_PLATFORM", None)

from PyQt6.QtCore import QPoint, QSettings, QStandardPaths, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.player import MPVPlayer  # noqa: E402
from app.title_bar import FramelessResizeFilter, resize_edges_at  # noqa: E402

user32 = ctypes.windll.user32
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetAsyncKeyState.restype = ctypes.c_short
VK_LBUTTON = 0x01
INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

START_X, START_Y, START_W, START_H = 300, 200, 1200, 720
DRAG_DISTANCE = 70
# Windows/DPI toleransi: hedef deltanin +-20 px'i veya %25'i (buyuk olan).
TOLERANCE_PX = 20
TOLERANCE_RATIO = 0.25
# Degismemesi gereken kenarin kabul edilen oynamasi.
STABLE_PX = 12
# Fiziksel girdi ONCESI imlecin hedefe oturmasi gereken tolerans.
CURSOR_TOLERANCE_PX = 2

VIDEO = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
APP = PLAYER = None
results = []
MPV_CALLS = []
counters = {"press_events": [], "start_calls": []}
input_report = {}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]

# yon: (nokta secici, (dx, dy), beklenen kenar degisimleri)
DIRECTIONS = {
    "left": (lambda r: (r.left() + 3, r.center().y()), (-DRAG_DISTANCE, 0),
             {"left": -DRAG_DISTANCE, "right": 0}),
    "right": (lambda r: (r.right() - 3, r.center().y()), (DRAG_DISTANCE, 0),
              {"right": DRAG_DISTANCE, "left": 0}),
    "top": (lambda r: (r.center().x(), r.top() + 3), (0, -DRAG_DISTANCE),
            {"top": -DRAG_DISTANCE, "bottom": 0}),
    "bottom": (lambda r: (r.center().x(), r.bottom() - 3), (0, DRAG_DISTANCE),
               {"bottom": DRAG_DISTANCE, "top": 0}),
    "top_left": (lambda r: (r.left() + 3, r.top() + 3),
                 (-DRAG_DISTANCE, -DRAG_DISTANCE),
                 {"left": -DRAG_DISTANCE, "top": -DRAG_DISTANCE,
                  "right": 0, "bottom": 0}),
    "top_right": (lambda r: (r.right() - 3, r.top() + 3),
                  (DRAG_DISTANCE, -DRAG_DISTANCE),
                  {"right": DRAG_DISTANCE, "top": -DRAG_DISTANCE,
                   "left": 0, "bottom": 0}),
    "bottom_left": (lambda r: (r.left() + 3, r.bottom() - 3),
                    (-DRAG_DISTANCE, DRAG_DISTANCE),
                    {"left": -DRAG_DISTANCE, "bottom": DRAG_DISTANCE,
                     "right": 0, "top": 0}),
    "bottom_right": (lambda r: (r.right() - 3, r.bottom() - 3),
                     (DRAG_DISTANCE, DRAG_DISTANCE),
                     {"right": DRAG_DISTANCE, "bottom": DRAG_DISTANCE,
                      "left": 0, "top": 0}),
}


def mark(text):
    print(text, flush=True)


def record(test, expected, measured, ok, evidence=""):
    status = "PASS" if ok is True else ("FAIL" if ok is False else "BLOCKED")
    results.append({"test": test, "status": status})
    print(f"RESULT|resize|{test}|SendInput(worker thread)|{expected}|{measured}|"
          f"{status}|{evidence}", flush=True)


def install_mpv_recorder():
    import mpv as mpv_module

    real_stop, real_terminate = mpv_module.MPV.stop, mpv_module.MPV.terminate

    def stop(self, *a, **k):
        MPV_CALLS.append("stop")
        return real_stop(self, *a, **k)

    def terminate(self, *a, **k):
        MPV_CALLS.append("terminate")
        return real_terminate(self, *a, **k)

    mpv_module.MPV.stop = stop
    mpv_module.MPV.terminate = terminate


def install_filter_probe():
    real_event_filter = FramelessResizeFilter.eventFilter
    real_start = FramelessResizeFilter._start_system_resize

    def counting_event_filter(self, watched, event):
        from PyQt6.QtCore import QEvent

        if event.type() == QEvent.Type.MouseButtonPress:
            try:
                position = self._window_position(watched, event)
                edges = resize_edges_at(self.player.rect(), position)
            except Exception:
                position, edges = None, None
            counters["press_events"].append({
                "watched": type(watched).__name__,
                "object": watched.objectName() or "-",
                "window_pos": (position.x(), position.y()) if position else None,
                "edges": int(edges.value) if edges else 0,
            })
        return real_event_filter(self, watched, event)

    def counting_start(self, edges):
        result = real_start(self, edges)
        counters["start_calls"].append({"edges": int(edges.value) if edges else 0,
                                        "returned": bool(result)})
        return result

    FramelessResizeFilter.eventFilter = counting_event_filter
    FramelessResizeFilter._start_system_resize = counting_start
    return real_event_filter, real_start


def cursor_pos():
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return (point.x, point.y)


def button_down():
    return bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)


def hwnd_of(widget):
    try:
        return int(widget.winId()) if widget is not None else 0
    except Exception:
        return 0


def win_rect(hwnd):
    rect = wintypes.RECT()
    user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    return (rect.left, rect.top, rect.right, rect.bottom)


def send(flag):
    """Tek mouse olayi gonderir ve SendInput'un DONUS degerini verir."""
    item = INPUT(type=INPUT_MOUSE, u=_U(mi=MOUSEINPUT(0, 0, 0, flag, 0, 0)))
    array = (INPUT * 1)(item)
    return int(user32.SendInput(1, array, ctypes.sizeof(INPUT)))


def input_worker(x0, y0, x1, y1, expected_hwnd, report):
    """YALNIZ Win32: hicbir Qt nesnesine dokunmaz (ayri thread).

    FAIL-CLOSED: onkosullar saglanmadan TEK bir mouse olayi bile
    gonderilmez. Aksi halde `SetCursorPos` etkisiz kaldiginda tiklama ve
    surukleme hedef disi bir pencerede gerceklesiyordu.
    """
    down_sent = False
    try:
        report["button_before"] = button_down()
        if report["button_before"]:
            report["blocked"] = "button_already_down"
            report["ok"] = False
            return
        user32.SetCursorPos(int(x0), int(y0))
        time.sleep(0.30)
        actual = cursor_pos()
        report["cursor_after_move"] = actual
        if (abs(actual[0] - int(x0)) > CURSOR_TOLERANCE_PX
                or abs(actual[1] - int(y0)) > CURSOR_TOLERANCE_PX):
            report["blocked"] = (f"cursor_not_on_target={actual}"
                                 f"!=({int(x0)},{int(y0)})")
            report["ok"] = False
            return
        point = wintypes.POINT(int(x0), int(y0))
        report["hwnd_at_start"] = int(user32.WindowFromPoint(point) or 0)
        report["hwnd_expected"] = expected_hwnd
        if report["hwnd_at_start"] != expected_hwnd:
            report["blocked"] = (f"hwnd_at_start={report['hwnd_at_start']}"
                                 f"!={expected_hwnd}")
            report["ok"] = False
            return
        if send(MOUSEEVENTF_LEFTDOWN) != 1:
            report["blocked"] = "sendinput_leftdown_failed"
            report["ok"] = False
            return
        down_sent = True
        time.sleep(0.25)
        report["button_after_down"] = button_down()
        steps = 24
        for index in range(1, steps + 1):
            user32.SetCursorPos(int(x0 + (x1 - x0) * index / steps),
                                int(y0 + (y1 - y0) * index / steps))
            time.sleep(0.02)
        time.sleep(0.25)
        report["cursor_before_up"] = cursor_pos()
        if send(MOUSEEVENTF_LEFTUP) != 1:
            report["blocked"] = "sendinput_leftup_failed"
            report["ok"] = False
            return
        down_sent = False
        time.sleep(0.30)
        report["button_after_up"] = button_down()
        report["cursor_final"] = cursor_pos()
        report["ok"] = True
    except Exception as exc:
        report["error"] = type(exc).__name__
        report["ok"] = False
    finally:
        if down_sent:
            # Sol tus BASILI kalmamali: hata veya erken donuste serbest birak.
            try:
                report["leftup_recovery"] = send(MOUSEEVENTF_LEFTUP)
            except Exception as exc:
                report["leftup_recovery_error"] = type(exc).__name__
            report["button_after_up"] = button_down()
        report["done"] = True


def contract_problems(report, x0, y0, x1, y1, expected_hwnd):
    problems = []
    blocked = report.get("blocked")
    if blocked:
        # Worker onkosulu saglamadigi icin girdi HIC gonderilmedi; eksik
        # LEFTDOWN/LEFTUP kayitlarini ayrica sorun olarak listelemek yanlis
        # iz surdururdu. Gercek neden tek basina raporlanir.
        return [f"input_precondition={blocked}"]
    if report.get("button_before"):
        problems.append("button_down_before_press")
    start = report.get("cursor_after_move")
    if not start or abs(start[0] - x0) > 2 or abs(start[1] - y0) > 2:
        problems.append(f"cursor_start={start}!=({x0},{y0})")
    if report.get("hwnd_at_start") != expected_hwnd:
        problems.append(f"hwnd_at_start={report.get('hwnd_at_start')}"
                        f"!={expected_hwnd}")
    if not report.get("button_after_down"):
        problems.append("button_not_down_after_LEFTDOWN")
    if report.get("button_after_up"):
        problems.append("button_still_down_after_LEFTUP")
    final = report.get("cursor_final")
    if not final or abs(final[0] - x1) > 2 or abs(final[1] - y1) > 2:
        problems.append(f"cursor_final={final}!=({x1},{y1})")
    if not report.get("ok"):
        problems.append(f"worker_error={report.get('error')}")
    return problems


def main():
    global APP, PLAYER

    parser = argparse.ArgumentParser()
    parser.add_argument("--direction", required=True, choices=sorted(DIRECTIONS))
    args = parser.parse_args()
    direction = args.direction

    if not (VIDEO and os.path.isfile(VIDEO)):
        print("RESULTS: failures=no_real_video (ORTAM EKSIGI)", flush=True)
        os._exit(2)

    QStandardPaths.setTestModeEnabled(True)
    settings = os.path.join(os.environ.get("TEMP", "."),
                            f"mlc_resize_{direction}-{os.getpid()}")
    os.makedirs(settings, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      settings)
    install_mpv_recorder()
    real_filter, real_start = install_filter_probe()

    original_cursor = cursor_pos()
    original_fg = int(user32.GetForegroundWindow() or 0)

    APP = QApplication([sys.argv[0]])
    PLAYER = MPVPlayer()
    PLAYER.setGeometry(START_X, START_Y, START_W, START_H)
    PLAYER.show()
    state = {"code": 0, "thread": None, "target": None}

    def finish():
        FramelessResizeFilter.eventFilter = real_filter
        FramelessResizeFilter._start_system_resize = real_start
        try:
            accepted = bool(PLAYER.close())
        except Exception as exc:
            accepted = False
            mark(f"TEARDOWN_WARNING {type(exc).__name__}")
        record("product_shutdown_path",
               "stop=1 terminate=1 sira=stop->terminate close=accepted",
               f"stop={MPV_CALLS.count('stop')} "
               f"terminate={MPV_CALLS.count('terminate')} "
               f"order={MPV_CALLS[:3]} close_accepted={accepted}",
               MPV_CALLS.count("stop") == 1
               and MPV_CALLS.count("terminate") == 1
               and MPV_CALLS[:2] == ["stop", "terminate"] and accepted)
        user32.SetCursorPos(*original_cursor)
        if original_fg:
            user32.SetForegroundWindow(wintypes.HWND(original_fg))
        APP.quit()

    def measure():
        """Worker bitti ve native donus oturdu: sonucu OKU."""
        target = state["target"]
        report = input_report
        problems = contract_problems(report, *target["path"],
                                     target["expected_hwnd"])
        after_qt = PLAYER.frameGeometry().getRect()
        after_win = win_rect(hwnd_of(PLAYER))
        before_qt = target["before_qt"]
        edges_map_before = {
            "left": before_qt[0], "top": before_qt[1],
            "right": before_qt[0] + before_qt[2],
            "bottom": before_qt[1] + before_qt[3],
        }
        edges_map_after = {
            "left": after_qt[0], "top": after_qt[1],
            "right": after_qt[0] + after_qt[2],
            "bottom": after_qt[1] + after_qt[3],
        }
        deltas = {key: edges_map_after[key] - edges_map_before[key]
                  for key in edges_map_before}
        presses = counters["press_events"]
        starts = counters["start_calls"]
        relevant = [p for p in presses if p["edges"]]
        geometry_problems = []
        for edge, wanted in target["expectations"].items():
            actual = deltas[edge]
            if wanted == 0:
                if abs(actual) > STABLE_PX:
                    geometry_problems.append(f"{edge}={actual}(sabit olmali)")
                continue
            tolerance = max(TOLERANCE_PX, abs(wanted) * TOLERANCE_RATIO)
            if abs(actual - wanted) > tolerance:
                geometry_problems.append(
                    f"{edge}={actual}(beklenen~{wanted}+-{int(tolerance)})")
        event_problems = []
        if len(relevant) != 1:
            event_problems.append(f"press_count={len(relevant)}")
        elif abs(relevant[0]["window_pos"][0] - target["local"][0]) > 3 or \
                abs(relevant[0]["window_pos"][1] - target["local"][1]) > 3:
            event_problems.append(f"press_pos={relevant[0]['window_pos']}"
                                  f"!={target['local']}")
        elif relevant[0]["edges"] != target["edges"]:
            event_problems.append(f"press_edges={relevant[0]['edges']}"
                                  f"!={target['edges']}")
        if len(starts) != 1:
            event_problems.append(f"start_calls={len(starts)}")
        elif not starts[0]["returned"]:
            event_problems.append("startSystemResize=False")

        mark(f"POST[{direction}] qt_frame={after_qt} win_rect={after_win} "
             f"deltas={deltas} presses={presses} starts={starts} "
             f"input={report}")

        measured = (f"intended={target['intended']} "
                    f"cursor_delta={target['cursor_delta']} "
                    f"before_qt={before_qt} after_qt={after_qt} "
                    f"before_win={target['before_win']} after_win={after_win} "
                    f"deltas={deltas} watched="
                    f"{relevant[0]['watched'] if relevant else None} "
                    f"press={len(relevant)} edges="
                    f"{relevant[0]['edges'] if relevant else None} "
                    f"start={starts} geometry_problems={geometry_problems} "
                    f"event_problems={event_problems}")
        if problems:
            record(f"resize_{direction}", "input sozlesmesi saglanir",
                   measured + f" input_problems={problems}", None,
                   "BLOCKED: INPUT_CONTRACT")
        else:
            record(f"resize_{direction}",
                   f"1 press@{target['local']} edges={target['edges']}, "
                   f"startSystemResize=True, kenarlar "
                   f"{target['expectations']}",
                   measured, not (geometry_problems or event_problems))
        finish()

    def poll_worker():
        if input_report.get("done"):
            poll.stop()
            state["thread"].join(timeout=5)
            input_report["thread_joined"] = not state["thread"].is_alive()
            # Native resize dongusunun oturmasi icin kisa bekleme.
            QTimer.singleShot(900, measure)

    poll = QTimer()
    poll.timeout.connect(poll_worker)

    def body():
        try:
            PLAYER.open_path(VIDEO)
            deadline = time.time() + 20
            while time.time() < deadline and not (PLAYER.mpv_player.duration or 0):
                APP.processEvents()
                time.sleep(0.05)
            mark(f"MARK_MEDIA_READY duration={PLAYER.mpv_player.duration}")
            frame = PLAYER.video_frame
            if frame.playlist_panel.is_open:
                frame.toggle_playlist_panel()
                frame.playlist_panel.finish_animation()
            PLAYER.showNormal()
            PLAYER.setGeometry(START_X, START_Y, START_W, START_H)
            deadline = time.time() + 4
            while time.time() < deadline:
                APP.processEvents()
                geo = PLAYER.geometry()
                if (abs(geo.x() - START_X) <= 2 and abs(geo.y() - START_Y) <= 2
                        and abs(geo.width() - START_W) <= 2
                        and abs(geo.height() - START_H) <= 2):
                    break
                time.sleep(0.05)
            target_hwnd = hwnd_of(PLAYER)
            for _ in range(6):
                if int(user32.GetForegroundWindow() or 0) == target_hwnd:
                    break
                user32.SetForegroundWindow(wintypes.HWND(target_hwnd))
                APP.processEvents()
                time.sleep(0.25)

            point_fn, delta, expectations = DIRECTIONS[direction]
            rect = PLAYER.frameGeometry()
            px, py = point_fn(rect)
            local = PLAYER.mapFromGlobal(QPoint(int(px), int(py)))
            edges = resize_edges_at(PLAYER.rect(), local)
            expected_hwnd = int(user32.WindowFromPoint(
                wintypes.POINT(int(px), int(py))) or 0)
            state["target"] = {
                "path": (px, py, px + delta[0], py + delta[1]),
                "expected_hwnd": expected_hwnd,
                "before_qt": rect.getRect(),
                "before_win": win_rect(target_hwnd),
                "local": (local.x(), local.y()),
                "edges": int(edges.value) if edges else 0,
                "expectations": expectations,
                "intended": delta,
                "cursor_delta": None,
            }
            mark(f"PRE[{direction}] qt_frame={rect.getRect()} "
                 f"qt_geo={PLAYER.geometry().getRect()} "
                 f"win_rect={state['target']['before_win']} "
                 f"point=({px},{py}) local={state['target']['local']} "
                 f"edges={state['target']['edges']} hwnd={expected_hwnd} "
                 f"dpr={PLAYER.devicePixelRatio()} "
                 f"foreground={int(user32.GetForegroundWindow() or 0) == target_hwnd} "
                 f"can_resize={PLAYER.title_bar.can_resize_window()} "
                 f"intended_delta={delta}")

            counters["press_events"].clear()
            counters["start_calls"].clear()
            worker = threading.Thread(
                target=input_worker,
                args=(px, py, px + delta[0], py + delta[1], expected_hwnd,
                      input_report),
                daemon=True)
            state["thread"] = worker
            worker.start()
            poll.start(100)
        except Exception:
            import traceback
            print("PYTHON_EXCEPTION " + traceback.format_exc().strip(),
                  flush=True)
            state["code"] = 90
            finish()

    QTimer.singleShot(0, body)
    exec_code = APP.exec()
    if state["target"] is not None and input_report.get("cursor_final"):
        start = input_report.get("cursor_after_move") or (0, 0)
        final = input_report["cursor_final"]
        mark(f"CURSOR_DELTA[{direction}] intended={state['target']['intended']} "
             f"actual=({final[0] - start[0]},{final[1] - start[1]})")
    mark(f"MARK_APP_EXEC_RETURNED code={exec_code}")
    failed = [r for r in results if r["status"] == "FAIL"]
    blocked = [r for r in results if r["status"] == "BLOCKED"]
    print(f"RESULTS: direction={direction} "
          f"failures={','.join(r['test'] for r in failed) or 'none'} "
          f"blocked={','.join(r['test'] for r in blocked) or 'none'}", flush=True)
    print("MARK_DONE", flush=True)
    os._exit(state["code"] or (1 if failed or blocked else 0))


if __name__ == "__main__":
    main()
