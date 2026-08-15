"""Fiziksel resize sonrasi YERLESIM/Z-ORDER degerlendirmesi (saf, Qt'siz).

`zorder_after_resize` satiri eskiden `PLAYER.resize()` ile programatik
boyut degistirip yalnizca geometriyi metin olarak basiyor ve karari goz
kontrolune birakiyordu. Karar artik bu saf fonksiyonla verilir; girdi,
gercek fiziksel resize sonrasinda toplanan global dikdortgen anlik
goruntusudur.

Dikdortgenler `(x, y, width, height)` bicimindedir.
"""

# Kenar hizalama toleransi (piksel). Qt yerlesimi ve DPI yuvarlamasi icin.
EDGE_TOLERANCE = 2
# Fiziksel resize hedefinden sapma toleransi.
RESIZE_TOLERANCE = 20
# Degismemesi gereken kenarin kabul edilen oynamasi.
STABLE_TOLERANCE = 12


def _left(rect):
    return rect[0]


def _top(rect):
    return rect[1]


def _right(rect):
    return rect[0] + rect[2]


def _bottom(rect):
    return rect[1] + rect[3]


def _intersects(a, b):
    return not (_right(a) <= _left(b) or _right(b) <= _left(a)
                or _bottom(a) <= _top(b) or _bottom(b) <= _top(a))


def resize_problems(before, after, expected):
    """Fiziksel resize GERCEKTEN istenen yonde oldu mu?"""
    problems = []
    edges = {
        "left": (_left(before), _left(after)),
        "top": (_top(before), _top(after)),
        "right": (_right(before), _right(after)),
        "bottom": (_bottom(before), _bottom(after)),
    }
    for edge, wanted in expected.items():
        start, end = edges[edge]
        delta = end - start
        if wanted == 0:
            if abs(delta) > STABLE_TOLERANCE:
                problems.append(f"{edge}={delta}(sabit olmali)")
        elif abs(delta - wanted) > max(RESIZE_TOLERANCE, abs(wanted) * 0.25):
            problems.append(f"{edge}={delta}(beklenen~{wanted})")
    return problems


def zorder_after_resize_problems(snapshot):
    """Resize sonrasi yerlesim + overlay + panel sahipligi degerlendirmesi.

    `snapshot` anahtarlari:
        client, title_bar, media_container, video_frame, playlist_host,
        playlist_panel, control_overlay  -> (x, y, w, h)
        panel_is_top_level               -> bool
        panel_inside_host_chain          -> bool
        overlay_visible                  -> bool
        overlay_opacity                  -> float
    """
    problems = []
    client = snapshot["client"]
    title = snapshot["title_bar"]
    container = snapshot["media_container"]
    video = snapshot["video_frame"]
    host = snapshot["playlist_host"]
    panel = snapshot["playlist_panel"]
    overlay = snapshot["control_overlay"]

    # --- Ana yerlesim ---
    if abs(_left(title) - _left(client)) > EDGE_TOLERANCE or \
            abs(_right(title) - _right(client)) > EDGE_TOLERANCE:
        problems.append("title_bar_not_full_width")
    if abs(_top(title) - _top(client)) > EDGE_TOLERANCE:
        problems.append("title_bar_not_at_top")
    if abs(_top(container) - _bottom(title)) > EDGE_TOLERANCE:
        problems.append("media_container_gap_under_title_bar")
    for edge, name in ((_left, "left"), (_right, "right"), (_bottom, "bottom")):
        if abs(edge(container) - edge(client)) > EDGE_TOLERANCE:
            problems.append(f"media_container_{name}_gap")

    # --- Video + playlist bolunmesi ---
    if abs(_left(video) - _left(container)) > EDGE_TOLERANCE:
        problems.append("video_not_at_container_left")
    if abs(_right(host) - _right(container)) > EDGE_TOLERANCE:
        problems.append("playlist_host_not_at_container_right")
    if abs(_left(host) - _right(video)) > EDGE_TOLERANCE:
        problems.append(f"split_gap={_left(host) - _right(video)}")
    if abs(_top(video) - _top(host)) > EDGE_TOLERANCE or \
            abs(_bottom(video) - _bottom(host)) > EDGE_TOLERANCE:
        problems.append("video_host_vertical_mismatch")
    if _left(panel) < _left(host) - EDGE_TOLERANCE or \
            _right(panel) > _right(host) + EDGE_TOLERANCE or \
            _top(panel) < _top(host) - EDGE_TOLERANCE or \
            _bottom(panel) > _bottom(host) + EDGE_TOLERANCE:
        problems.append("panel_outside_host")
    if _intersects(panel, video):
        problems.append("panel_intersects_video")
    if snapshot.get("panel_is_top_level"):
        problems.append("panel_is_top_level")
    if not snapshot.get("panel_inside_host_chain", True):
        problems.append("panel_not_in_host_chain")

    # --- Overlay ---
    if not snapshot.get("overlay_visible", True):
        problems.append("overlay_hidden")
    if float(snapshot.get("overlay_opacity", 1.0)) <= 0.0:
        problems.append("overlay_opacity_zero")
    if _left(overlay) < _left(video) - EDGE_TOLERANCE or \
            _right(overlay) > _right(video) + EDGE_TOLERANCE or \
            _top(overlay) < _top(video) - EDGE_TOLERANCE or \
            _bottom(overlay) > _bottom(video) + EDGE_TOLERANCE:
        problems.append("overlay_outside_video")
    if abs(_bottom(overlay) - _bottom(video)) > EDGE_TOLERANCE:
        problems.append("overlay_not_bottom_aligned")
    # Resize sonrasi eski genislikte kalmis overlay: video genisligiyle
    # ayni olmali.
    if abs(overlay[2] - video[2]) > EDGE_TOLERANCE:
        problems.append(f"overlay_width={overlay[2]}!=video_width={video[2]}")

    # --- Overlay ici kontroller ---
    for name, rect in (snapshot.get("controls") or {}).items():
        if _left(rect) < _left(overlay) - EDGE_TOLERANCE or \
                _right(rect) > _right(overlay) + EDGE_TOLERANCE or \
                _top(rect) < _top(overlay) - EDGE_TOLERANCE or \
                _bottom(rect) > _bottom(overlay) + EDGE_TOLERANCE:
            problems.append(f"control_outside_overlay:{name}")

    # --- Native hit / z-order ---
    for name, actual in (snapshot.get("control_hits") or {}).items():
        if actual != "overlay":
            problems.append(f"control_hit:{name}={actual}")
    # Panel merkezi VideoFrame'e DUSMEMELI ve baska bir surece ait
    # olmamalidir. Gomulu panel kendi surecimizde host/panel HWND'sine
    # dusebilir; bu kabul edilir.
    panel_hit = snapshot.get("panel_hit")
    if panel_hit is not None and panel_hit in ("video_frame", "other_process"):
        problems.append(f"panel_hit={panel_hit}")
    if snapshot.get("foreground_is_player") is False:
        problems.append("player_not_foreground")
    return problems
