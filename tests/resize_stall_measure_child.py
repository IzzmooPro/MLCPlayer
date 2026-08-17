# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Gerçek pencerede resize sürüklemesi sırasında bant senkronunu ÖLÇER.

16 Ağustos 2026'daki ölçümün eksik kalan yarısıdır. O tur `sync_subtitle_
safe_band()` maliyetini SABİT boyutta ölçtü; önbellek her şeyi yuttuğu için
libmpv'ye tek yazım gitmedi ve p95 0,07 ms göründü. Gerçek sürüklemede boyut
her adımda değişir, önbellek hiç tutmaz ve her adım senkron bir
`mpv_set_property` yapar.

Bu child GERÇEK Windows penceresi + GERÇEK video ile sürüklemeyi taklit eder
ve ürünün KENDİ çağrısını (`resizeEvent` zinciri içinden) saran bir sarmalayıcı
ile süre ölçer. Ölçüm sözleşmesi: stdout'ta TEK `RESIZE_STALL_JSON` satırı.

Ortam:
    MLC_NATIVE_TEST_VIDEO   gerçek video yolu (ZORUNLU)
    MLC_RESIZE_STEPS        sürükleme adım sayısı (varsayılan 120)
"""
import json
import os
import statistics
import sys
import time

# GERÇEK platform şart: offscreen'de mpv swapchain kurmaz ve ölçülen kilit
# beklemesi HİÇ oluşmaz. Bu pop yalnız bu child sürecini etkiler.
os.environ.pop("QT_QPA_PLATFORM", None)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.environ["PATH"] = os.path.join(project_root, "bin") + os.pathsep + os.environ["PATH"]

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from app.player import MPVPlayer

VIDEO = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
STEPS = int(os.environ.get("MLC_RESIZE_STEPS", "120"))


def phase(name):
    print(f"PHASE {name}", file=sys.stderr, flush=True)


def _wait_for_playback(app, player, timeout=20.0):
    """Video GERÇEKTEN oynayana kadar bekler (süre > 0 ve çekirdek boşta değil)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if float(getattr(player, "duration", 0) or 0) > 0 and not player._core_idle:
            return True
        time.sleep(0.02)
    return False


def _stats(samples):
    if not samples:
        return {}
    ordered = sorted(samples)
    index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return {
        "count": len(ordered),
        "mean_ms": round(statistics.fmean(ordered), 3),
        "median_ms": round(statistics.median(ordered), 3),
        "p95_ms": round(ordered[index], 3),
        "max_ms": round(max(ordered), 3),
    }


def main():
    report = {"video": os.path.basename(VIDEO), "steps_requested": STEPS}
    if not VIDEO or not os.path.exists(VIDEO):
        report["error"] = "MLC_NATIVE_TEST_VIDEO yok veya bulunamadi"
        print("RESIZE_STALL_JSON " + json.dumps(report), flush=True)
        return 2

    phase("qapplication")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    settings_dir = os.environ.get("MLC_RESIZE_SETTINGS")
    if settings_dir:
        QSettings.setPath(QSettings.Format.IniFormat,
                          QSettings.Scope.UserScope, settings_dir)

    phase("mpvplayer_init")
    player = MPVPlayer()
    phase("mpvplayer_ready")
    try:
        player.resize(1280, 800)
        player.show()
        app.processEvents()
        phase("shown")

        player.open_path(VIDEO)
        phase("file_opened")
        report["playback_started"] = _wait_for_playback(app, player)
        if not report["playback_started"]:
            report["error"] = "video oynamaya baslamadi"
            print("RESIZE_STALL_JSON " + json.dumps(report), flush=True)
            return 3
        phase("playing")

        frame = player.video_frame
        # ÜRÜNÜN KENDİ çağrısını sar: `resizeEvent` zinciri değişmez, yalnız
        # süre ve yazım olup olmadığı kaydedilir.
        samples = []
        writes = []
        original = frame.sync_subtitle_safe_band

        def timed():
            before = frame._subtitle_band_state
            start = time.perf_counter()
            result = original()
            elapsed = (time.perf_counter() - start) * 1000.0
            samples.append(elapsed)
            after = frame._subtitle_band_state
            wrote = (before is None or after is None
                     or before[1] != after[1])
            writes.append(bool(wrote))
            return result

        frame.sync_subtitle_safe_band = timed

        phase("drag")
        # Gerçek kenar sürüklemesi: pencere yüksekliği adım adım küçülür ve
        # her adımda Qt olayları işlenir (mpv swapchain'i yeniden kurar).
        # ADIM SÜRESİ de ölçülür: bizim bant yazımımızın toplam sürüklemenin
        # NE KADARI olduğunu bilmeden "kök neden" denemez.
        step_times = []
        start_height, end_height = 800, 800 - STEPS
        drag_start = time.perf_counter()
        for height in range(start_height, end_height, -1):
            step_start = time.perf_counter()
            player.resize(1280, height)
            app.processEvents()
            step_times.append((time.perf_counter() - step_start) * 1000.0)
        report["drag_wall_ms"] = round(
            (time.perf_counter() - drag_start) * 1000.0, 1)
        report["step"] = _stats(step_times)
        phase("drag_done")

        # Sürükleme durdu: ertelenmiş bant yazımı burada uygulanmalı.
        # Bu süre KULLANICIYI ETKİLEMEZ (sürükleme bitmiştir) ama ölçülür.
        settle_start = time.perf_counter()
        for _ in range(10):
            app.processEvents()
            time.sleep(0.01)
        report["settle_ms"] = round(
            (time.perf_counter() - settle_start) * 1000.0, 1)
        # ZAYIF DEĞİL: bandın var olması yetmez, DOĞRU olması gerekir.
        # Sürükleme sonrası MPV'deki gerçek marj, son boyut için beklenen
        # marjla birebir aynı olmalı. Aksi hâlde erteleme davranışı
        # değiştirmiş, yani gereken yazımı yutmuş demektir.
        expected = frame.subtitle_safe_margin(frame.subtitle_scale_reference())
        applied = frame._subtitle_band_state
        report["expected_margin"] = expected
        report["applied_margin"] = applied[1][0] if applied else None
        report["mpv_margin_readback"] = getattr(
            player.mpv_player, "sub_margin_y", None)
        report["band_correct_after_drag"] = (
            applied is not None and applied[1][0] == expected)

        writing = [s for s, w in zip(samples, writes) if w]
        idle = [s for s, w in zip(samples, writes) if not w]
        report["sync_calls"] = len(samples)
        report["write_calls"] = sum(writes)
        report["all"] = _stats(samples)
        report["writing_only"] = _stats(writing)
        report["cached_only"] = _stats(idle)
        report["total_blocked_ms"] = round(sum(samples), 1)
        # BİZİM payımız: bant senkronu / toplam sürükleme.
        if report.get("drag_wall_ms"):
            report["our_share_pct"] = round(
                100.0 * sum(samples) / report["drag_wall_ms"], 1)
        print("RESIZE_STALL_JSON " + json.dumps(report), flush=True)
        return 0
    finally:
        phase("teardown")
        # Ürünün KENDİ kapanış yolu (`closeEvent` → stop → terminate).
        try:
            player.close()
        except Exception:
            try:
                player.mpv_player.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    finally:
        phase("exit")
        sys.stdout.flush()
        sys.stderr.flush()
        # libmpv yükleyen child'lar normal finalizasyona GİRMEZ
        # (bkz. main.py:130 ve test_child_shutdown_contract_regressions).
        os._exit(code)
