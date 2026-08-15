"""Fiziksel slider olcumleri icin HEDEF SECIMI (saf, Qt'siz).

Sabit bir yuzde hedefi (ornegin `%25`) mevcut degere denk geldiginde
tiklama gercekten calissa bile deger degismez ve olcum sahte FAIL uretir.
Gercek ornek: ses aralig 0-175, mevcut deger 44, sabit %25 hedefi ~44 ->
`44->44` FAIL.

Bu modul mevcut degerden UZAK, aralik icinde ve ayni degere yuvarlanmayan
bir hedef secer.
"""

# Aday oranlar: alt ve ust bolgeden birer guvenli nokta.
LOW_RATIO = 0.20
HIGH_RATIO = 0.80


def candidate_values(minimum, maximum):
    """Aralik icinde iki guvenli aday deger."""
    span = max(0, int(maximum) - int(minimum))
    low = int(round(minimum + span * LOW_RATIO))
    high = int(round(minimum + span * HIGH_RATIO))
    return low, high


def pick_far_target(minimum, maximum, current):
    """Mevcut degere MUTLAK olarak daha uzak adayi secer.

    Esitlikte deterministik olarak ust aday secilir. Donen deger daima
    [minimum, maximum] araligindadir.
    """
    minimum, maximum = int(minimum), int(maximum)
    if maximum < minimum:
        minimum, maximum = maximum, minimum
    current = max(minimum, min(maximum, int(current)))
    low, high = candidate_values(minimum, maximum)
    if abs(high - current) >= abs(low - current):
        return high
    return low


def target_x_for_value(value, minimum, maximum, width):
    """Hedef degerin slider ICINDEKI x koordinati.

    `ClickableSlider._value_at()` ile ayni eslemenin tersidir:
        value = minimum + span * (x / width)
    """
    span = max(1, int(maximum) - int(minimum))
    ratio = (int(value) - int(minimum)) / span
    ratio = min(1.0, max(0.0, ratio))
    return int(round(ratio * max(1, int(width))))


def value_tolerance_for_width(minimum, maximum, width):
    """Piksel yuvarlamasini kapsayan DAR tolerans (yaklasik 2 piksel)."""
    span = max(1, int(maximum) - int(minimum))
    per_pixel = span / max(1, int(width))
    return max(1, int(round(2 * per_pixel)))
