"""Model fiyatlandırması ve maliyet hesabı — PROJECT.md §5 (MAX_MALIYET_USD).

Fiyatlar 1M token başına USD. Bilinmeyen bir model için **en pahalı bilinen
fiyat** kullanılır: maliyet tavanı bir güvenlik mekanizmasıdır, bilinmezliği
"ücretsiz" saymak tavanı sessizce devre dışı bırakırdı.
"""

from __future__ import annotations

from decimal import Decimal

MILLION = Decimal("1000000")

# model kimliği -> (girdi $/MTok, çıktı $/MTok)
PRICES: dict[str, tuple[Decimal, Decimal]] = {
    # Anthropic
    "claude-fable-5": (Decimal("10"), Decimal("50")),
    "claude-opus-5": (Decimal("5"), Decimal("25")),
    "claude-opus-4-8": (Decimal("5"), Decimal("25")),
    "claude-opus-4-7": (Decimal("5"), Decimal("25")),
    "claude-opus-4-6": (Decimal("5"), Decimal("25")),
    # Sonnet 5'in 31.08.2026'ya kadar tanıtım fiyatı $2/$10'dur. Bilinçli
    # olarak liste fiyatı yazıldı: tavan hesabı gerçek maliyetin ÜSTÜNDE
    # kalmalı, altında değil.
    "claude-sonnet-5": (Decimal("3"), Decimal("15")),
    "claude-sonnet-4-6": (Decimal("3"), Decimal("15")),
    "claude-haiku-4-5": (Decimal("1"), Decimal("5")),
}

# Yerel modeller ücretsizdir.
FREE_PREFIXES: tuple[str, ...] = ("ollama/", "llama", "qwen", "mistral", "gemma", "phi")

# Önbellek çarpanları (girdi fiyatına göre).
CACHE_WRITE_MULTIPLIER = Decimal("1.25")
CACHE_READ_MULTIPLIER = Decimal("0.1")

_MOST_EXPENSIVE = max(PRICES.values(), key=lambda p: p[1])


def is_free(model: str) -> bool:
    lowered = model.lower()
    return any(lowered.startswith(prefix) for prefix in FREE_PREFIXES)


def price_for(model: str) -> tuple[tuple[Decimal, Decimal], bool]:
    """(girdi, çıktı) fiyatı ve fiyatın bilinip bilinmediği.

    Bilinmeyen model için en pahalı bilinen fiyat döner — tahmin yukarı
    yuvarlanır, çünkü bu değer bir harcama tavanını besliyor.
    """
    if is_free(model):
        return (Decimal("0"), Decimal("0")), True
    known = PRICES.get(model)
    if known is not None:
        return known, True
    return _MOST_EXPENSIVE, False


def estimate_cost(
    model: str,
    token_girdi: int,
    token_cikti: int,
    onbellek_yazma: int = 0,
    onbellek_okuma: int = 0,
) -> Decimal:
    """Bir çağrının maliyetini USD olarak hesaplar.

    Önbellek token'ları girdi fiyatının katlarıyla ücretlendirilir:
    yazma ~1.25x, okuma ~0.1x.
    """
    (girdi_fiyat, cikti_fiyat), _ = price_for(model)
    if girdi_fiyat == 0 and cikti_fiyat == 0:
        return Decimal("0.00000")

    toplam = (
        Decimal(token_girdi) * girdi_fiyat
        + Decimal(token_cikti) * cikti_fiyat
        + Decimal(onbellek_yazma) * girdi_fiyat * CACHE_WRITE_MULTIPLIER
        + Decimal(onbellek_okuma) * girdi_fiyat * CACHE_READ_MULTIPLIER
    ) / MILLION
    # Mesaj şeması decimal(8,5) bekliyor (§7.1).
    return toplam.quantize(Decimal("0.00001"))
