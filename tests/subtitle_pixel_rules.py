# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı görüntü kabulü için SAF piksel analiz kuralları.

Bu modül Qt, MPV, dosya sistemi veya ağ KULLANMAZ. Girdi tek biçimdir:

    frame = {"width": W, "height": H, "data": <bytes, RGB888, dolgu yok>}

Neden ayrı modül
----------------
"Ekranda altyazı gerçekten göründü mü, kutu gerçekten çizildi mi, kenarlık
yazıdan ayrı bir piksel kümesi mi?" sorularının cevabı ölçülebilir ve
kendi başına test edilebilir olmalı. Child süreç yalnız ölçüm toplar;
karar mantığı burada durur.

Tasarım kararları
-----------------
- Toplam ekran farkı TEK BAŞINA kanıt sayılmaz: her ölçüm ya bir renk
  maskesi ya da AYNI KARE üzerinde alınmış iki görüntünün farkıdır.
- Tolerans her çağrıda AÇIKÇA verilir; modül gizli tolerans uydurmaz.
- Bulunamayan maske `count=0, bbox=None` döner; çağıran taraf bunu
  PASS'a çeviremez.
"""

# Kanal başına varsayılan yok: çağıran taraf toleransı açıkça verir.


def make_frame(width, height, data):
    """Ölçüm karesi. `data` RGB888, satır dolgusu OLMADAN verilmelidir."""
    width = int(width)
    height = int(height)
    if width <= 0 or height <= 0:
        raise ValueError("frame_empty")
    if len(data) != width * height * 3:
        raise ValueError(f"frame_size_mismatch {len(data)} != {width*height*3}")
    return {"width": width, "height": height, "data": bytes(data)}


def full_region(frame):
    return (0, 0, frame["width"] - 1, frame["height"] - 1)


def clamp_region(frame, region):
    """Region'ı kare içine kırpar; geçersizse None."""
    if region is None:
        return full_region(frame)
    left, top, right, bottom = (int(v) for v in region)
    left = max(0, left)
    top = max(0, top)
    right = min(frame["width"] - 1, right)
    bottom = min(frame["height"] - 1, bottom)
    if left > right or top > bottom:
        return None
    return (left, top, right, bottom)


def pixel(frame, x, y):
    index = (y * frame["width"] + x) * 3
    data = frame["data"]
    return (data[index], data[index + 1], data[index + 2])


def matches(rgb, target, tol):
    """Kanal başına mutlak fark toleransı."""
    return (abs(rgb[0] - target[0]) <= tol
            and abs(rgb[1] - target[1]) <= tol
            and abs(rgb[2] - target[2]) <= tol)


def _empty_stats():
    return {"count": 0, "bbox": None, "centre": None, "scanned": 0}


def _finish(count, left, top, right, bottom, scanned):
    if count == 0:
        stats = _empty_stats()
        stats["scanned"] = scanned
        return stats
    return {"count": count, "bbox": (left, top, right, bottom),
            "centre": ((left + right) // 2, (top + bottom) // 2),
            "scanned": scanned}


def scan_color(frame, target, tol, region=None):
    """Verilen renge yakın piksellerin sayısı ve sınırlayıcı dikdörtgeni."""
    box = clamp_region(frame, region)
    if box is None:
        return _empty_stats()
    left, top, right, bottom = box
    data = frame["data"]
    width = frame["width"]
    tr, tg, tb = target[0], target[1], target[2]
    count = 0
    min_x, min_y, max_x, max_y = right, bottom, left, top
    scanned = 0
    for y in range(top, bottom + 1):
        base = (y * width + left) * 3
        for x in range(left, right + 1):
            index = base + (x - left) * 3
            scanned += 1
            if (abs(data[index] - tr) <= tol
                    and abs(data[index + 1] - tg) <= tol
                    and abs(data[index + 2] - tb) <= tol):
                count += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    return _finish(count, min_x, min_y, max_x, max_y, scanned)


def scan_changed(before, after, threshold, region=None):
    """AYNI KARE üzerinde iki görüntü arasındaki değişen piksel maskesi.

    Video karesi sabit tutulduğu için değişen pikseller altyazı
    katmanıdır. `threshold` kanal başına en büyük farktır.
    """
    if (before["width"] != after["width"]
            or before["height"] != after["height"]):
        raise ValueError("frame_geometry_mismatch")
    box = clamp_region(before, region)
    if box is None:
        return _empty_stats()
    left, top, right, bottom = box
    a, b = before["data"], after["data"]
    width = before["width"]
    count = 0
    min_x, min_y, max_x, max_y = right, bottom, left, top
    scanned = 0
    for y in range(top, bottom + 1):
        row = y * width
        for x in range(left, right + 1):
            index = (row + x) * 3
            scanned += 1
            if (abs(a[index] - b[index]) > threshold
                    or abs(a[index + 1] - b[index + 1]) > threshold
                    or abs(a[index + 2] - b[index + 2]) > threshold):
                count += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    return _finish(count, min_x, min_y, max_x, max_y, scanned)


def scan_changed_color(before, after, threshold, target, tol, region=None):
    """Hem DEĞİŞMİŞ hem de hedef renge yakın pikseller.

    Videonun kendi pikselleri tesadüfen hedef renge yakın olabilir; bu
    yüzden renk maskesi tek başına kanıt sayılmaz.
    """
    if (before["width"] != after["width"]
            or before["height"] != after["height"]):
        raise ValueError("frame_geometry_mismatch")
    box = clamp_region(before, region)
    if box is None:
        return _empty_stats()
    left, top, right, bottom = box
    a, b = before["data"], after["data"]
    width = before["width"]
    tr, tg, tb = target[0], target[1], target[2]
    count = 0
    min_x, min_y, max_x, max_y = right, bottom, left, top
    scanned = 0
    for y in range(top, bottom + 1):
        row = y * width
        for x in range(left, right + 1):
            index = (row + x) * 3
            scanned += 1
            if not (abs(a[index] - b[index]) > threshold
                    or abs(a[index + 1] - b[index + 1]) > threshold
                    or abs(a[index + 2] - b[index + 2]) > threshold):
                continue
            if (abs(b[index] - tr) <= tol
                    and abs(b[index + 1] - tg) <= tol
                    and abs(b[index + 2] - tb) <= tol):
                count += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    return _finish(count, min_x, min_y, max_x, max_y, scanned)


def bbox_size(bbox):
    if not bbox:
        return (0, 0)
    left, top, right, bottom = bbox
    return (right - left + 1, bottom - top + 1)


def bbox_area(bbox):
    width, height = bbox_size(bbox)
    return width * height


def bbox_centre(bbox):
    if not bbox:
        return None
    left, top, right, bottom = bbox
    return ((left + right) // 2, (top + bottom) // 2)


def fill_ratio(count, bbox):
    """Maskenin kendi sınırlayıcı dikdörtgenini ne kadar DOLDURDUĞU.

    Yalnız yazı çizildiğinde bu oran düşüktür; gerçek bir arka plan
    kutusu çizildiğinde 1'e yaklaşır.
    """
    area = bbox_area(bbox)
    if area <= 0:
        return 0.0
    return count / float(area)


def longest_run(frame, target, tol, region=None):
    """Hedef renge yakın piksellerin EN UZUN yatay kesintisiz dizisi.

    Neden gerekli
    -------------
    Doluluk oranı (`fill_ratio`) iki farklı genişlikte satır olduğunda
    yanıltıcıdır: iki ayrı kutunun BİRLEŞİK sınırlayıcı dikdörtgeni
    doğal olarak boş köşeler içerir. "Gerçekten dolu bir kutu çizildi
    mi?" sorusunun ayırt edici ölçüsü satır içi kesintisiz uzunluktur:
    yalnız yazıda glif gövdeleri arasındaki boşluklar diziyi kısa
    tutar, gerçek kutuda ise dizi satır genişliğine yaklaşır.

    Dönüş: `{"best": en uzun dizi, "row": o satırın y'si,
             "rows_over_half": yarı genişliği aşan satır sayısı}`
    """
    box = clamp_region(frame, region)
    if box is None:
        return {"best": 0, "row": None, "rows_over_half": 0}
    left, top, right, bottom = box
    data = frame["data"]
    width = frame["width"]
    tr, tg, tb = target[0], target[1], target[2]
    span = right - left + 1
    best, best_row, rows_over_half = 0, None, 0
    for y in range(top, bottom + 1):
        row = y * width
        current = 0
        row_best = 0
        for x in range(left, right + 1):
            index = (row + x) * 3
            if (abs(data[index] - tr) <= tol
                    and abs(data[index + 1] - tg) <= tol
                    and abs(data[index + 2] - tb) <= tol):
                current += 1
                if current > row_best:
                    row_best = current
            else:
                current = 0
        if row_best * 2 >= span:
            rows_over_half += 1
        if row_best > best:
            best, best_row = row_best, y
    return {"best": best, "row": best_row, "rows_over_half": rows_over_half}


def changed_longest_run(before, after, threshold, region=None):
    """DEĞİŞEN piksellerin en uzun yatay dizisi (renkten bağımsız)."""
    if (before["width"] != after["width"]
            or before["height"] != after["height"]):
        raise ValueError("frame_geometry_mismatch")
    box = clamp_region(before, region)
    if box is None:
        return {"best": 0, "row": None, "rows_over_half": 0}
    left, top, right, bottom = box
    a, b = before["data"], after["data"]
    width = before["width"]
    span = right - left + 1
    best, best_row, rows_over_half = 0, None, 0
    for y in range(top, bottom + 1):
        row = y * width
        current = 0
        row_best = 0
        for x in range(left, right + 1):
            index = (row + x) * 3
            if (abs(a[index] - b[index]) > threshold
                    or abs(a[index + 1] - b[index + 1]) > threshold
                    or abs(a[index + 2] - b[index + 2]) > threshold):
                current += 1
                if current > row_best:
                    row_best = current
            else:
                current = 0
        if row_best * 2 >= span:
            rows_over_half += 1
        if row_best > best:
            best, best_row = row_best, y
    return {"best": best, "row": best_row, "rows_over_half": rows_over_half}


def solid_box_ratio(run, bbox):
    """En uzun dizinin kutu genişliğine oranı (0..1)."""
    width = bbox_size(bbox)[0]
    if width <= 0:
        return 0.0
    return min(1.0, run / float(width))


def contains(outer, inner, slack=0):
    """`inner` dikdörtgeni `outer` içinde mi (isteğe bağlı pay ile)?"""
    if not outer or not inner:
        return False
    return (inner[0] >= outer[0] - slack and inner[1] >= outer[1] - slack
            and inner[2] <= outer[2] + slack and inner[3] <= outer[3] + slack)


def padding(inner, outer):
    """Kutunun harflerden dört yönde bıraktığı boşluk (piksel).

    Negatif değer kutunun metni KESTİĞİ anlamına gelir.
    """
    if not inner or not outer:
        return None
    return {"left": inner[0] - outer[0], "top": inner[1] - outer[1],
            "right": outer[2] - inner[2], "bottom": outer[3] - inner[3]}


def padding_problems(pads, minimum, maximum):
    """Dört yön boşluğu kabul aralığında mı? Boş liste = kabul."""
    if not pads:
        return ["padding_unmeasurable"]
    problems = []
    for side in ("left", "top", "right", "bottom"):
        value = pads[side]
        if value < minimum:
            problems.append(f"{side}={value}<{minimum}")
        elif value > maximum:
            problems.append(f"{side}={value}>{maximum}")
    return problems


def intersection(first, second):
    if not first or not second:
        return None
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    if left > right or top > bottom:
        return None
    return (left, top, right, bottom)


def overlap_ratio(bbox, other):
    """`bbox`in `other` ile kesişen alan oranı (0..1)."""
    area = bbox_area(bbox)
    if area <= 0:
        return 0.0
    return bbox_area(intersection(bbox, other)) / float(area)


def growth_ratio(smaller, larger):
    """İki ölçünün oranı; taban 0 ise 0 döner (sahte büyüme yok)."""
    if not smaller or not larger:
        return 0.0
    return (larger / float(smaller)) if smaller > 0 else 0.0


def horizontal_centre_offset(bbox, region):
    """Maskenin yatay merkezinin bölge merkezinden sapması (piksel)."""
    centre = bbox_centre(bbox)
    if centre is None or not region:
        return None
    region_centre = (region[0] + region[2]) // 2
    return centre[0] - region_centre
