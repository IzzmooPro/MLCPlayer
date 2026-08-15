"""Fiziksel kabul olcumlerinin TOLERANS formulleri (saf, Qt'siz).

Ayri modul olmasinin nedeni: bu formuller hem native child'da kullanilir
hem de normal pytest paketinde regresyonla kilitlenir. Genis tolerans
gercek bir yanlis seek'i PASS yapabildigi icin degerler burada TEK yerde
tanimlanir.
"""
import math

# Zaman toleransinin alt/ust sinirlari. Urun gercek `time_pos` hedefini
# izler; olculen sapma bir saniyenin altindadir. Ust sinir, cok uzun
# videolarda bile 15 sn'yi asmaz.
MIN_TIME_TOLERANCE_S = 3.0
MAX_TIME_TOLERANCE_S = 15.0
TIME_TOLERANCE_RATIO = 0.001


def slider_value_tolerance(span, width):
    """Slider degeri toleransi: PIKSEL cozunurlugunden turetilir.

    Bir piksel `ceil(span / width)` birime karsilik gelir; kabul edilen
    fark en fazla iki pikseldir. Sabit bir +-20 degeri, genis timeline'da
    ~%2'lik gercek sapmayi gizlerdi.
    """
    step = math.ceil(max(1, int(span)) / max(1, int(width)))
    return max(3, 2 * step)


def seek_time_tolerance(duration):
    """Seek zamani toleransi (saniye).

    Sure ile hafif olceklenir ama 15 sn'yi asamaz; boylece 3 saatlik bir
    videoda bile yanlis seek yakalanir.
    """
    return max(MIN_TIME_TOLERANCE_S,
               min(MAX_TIME_TOLERANCE_S,
                   float(duration) * TIME_TOLERANCE_RATIO))
