"""Girdi sınırlama ve görev metninin veri olarak taşınması — tehdit T3.

Prompt injection'a karşı savunma "kötü niyetli cümleleri tespit etmek"
değildir; o yarış kaybedilir. Savunma **yapısaldır**: görev metni asla
talimat konumuna girmez. Sistem promptu sabit dosyadan gelir, kullanıcı
metni ayrı ve sınırlandırılmış bir veri bloğunda taşınır.

Bu modül üç iş yapar: metni sınırlar, sınırlayıcıyı taklit eden içeriği
etkisizleştirir, ve metinde sır varsa görevi hiç başlatmaz.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.security import secret_scan

# Sınırlayıcı bilinçli olarak "doğal metinde kazara oluşamayacak" biçimde.
DELIMITER_OPEN = "<<<KULLANICI_GOREVI>>>"
DELIMITER_CLOSE = "<<<KULLANICI_GOREVI_SON>>>"

# Görünmez yön değiştirme ve sıfır genişlikli karakterler: metni insana
# göründüğünden farklı okutabilirler.
_INVISIBLE = re.compile(r"[​-‏‪-‮⁦-⁩﻿]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class InputRejected(ValueError):
    """Görev metni kabul edilmedi. Mesajı metnin kendisini içermez."""


@dataclass(frozen=True)
class SanitizedTask:
    text: str
    original_length: int
    stripped_invisible: int
    neutralized_delimiters: int


def sanitize(text: str, max_chars: int) -> SanitizedTask:
    """Görev metnini temizler ve sınırlar.

    İstisna mesajları metni yankılamaz: görev metni saldırgan kontrolündedir
    ve bir hata mesajı log'a veya arayüze düşebilir.
    """
    if text is None:
        raise InputRejected("görev metni yok")

    original_length = len(text)
    cleaned, invisible_count = _INVISIBLE.subn("", text)
    cleaned = _CONTROL.sub("", cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        raise InputRejected("görev metni boş")
    if len(cleaned) > max_chars:
        raise InputRejected(
            f"görev metni çok uzun ({len(cleaned)} karakter, tavan {max_chars})"
        )

    findings = secret_scan.scan(cleaned)
    if findings:
        # Anahtar sohbet kutusuna yapıştırılmış. Görev başlatılmaz: metin
        # aksi hâlde transkripte ve LLM sağlayıcısına giderdi.
        turler = ", ".join(sorted({f.tur for f in findings}))
        raise InputRejected(
            f"görev metninde sır tespit edildi ({turler}); "
            f"API anahtarları görev kutusuna değil anahtar alanına girilir"
        )

    neutralized = cleaned.count(DELIMITER_OPEN) + cleaned.count(DELIMITER_CLOSE)
    cleaned = cleaned.replace(DELIMITER_OPEN, "<<<>>>").replace(
        DELIMITER_CLOSE, "<<<>>>"
    )

    return SanitizedTask(
        text=cleaned,
        original_length=original_length,
        stripped_invisible=invisible_count,
        neutralized_delimiters=neutralized,
    )


def as_data_block(task_text: str) -> str:
    """Görev metnini sınırlandırılmış veri bloğuna sarar.

    Blok içeriği veridir. Prompt'lar (insan tarafından yazılan) bu bloğun
    içindekini talimat olarak işlememeleri gerektiğini açıkça söyler.
    """
    return f"{DELIMITER_OPEN}\n{task_text}\n{DELIMITER_CLOSE}"
