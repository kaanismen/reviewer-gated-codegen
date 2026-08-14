"""Rol bazlı API anahtarı kasası — PROJECT.md §6, tehdit T7 ve T8.

Son kullanıcı her agent için kendi anahtarını girebilir. Bu, sisteme
üçüncü taraf kimlik bilgisi emanet etmek demektir; dolayısıyla kasanın
sözleşmesi dar tutulmuştur:

1. **Anahtar diske yazılmaz.** Yalnızca süreç belleğinde durur; konteyner
   yeniden başlayınca kaybolur. Bu bir eksiklik değil, tasarımdır.
2. **Anahtar geri okunamaz.** Dışarıya yalnızca maskeli parmak izi verilir;
   `get()` yalnızca sağlayıcı istemcisini kuran kod tarafından çağrılır.
3. **Anahtar log'a ve transkripte giremez.** `SecretStr` kazara `repr`/`str`
   sızıntısını, `redact()` ise transkripte giden metinleri kapatır.
4. **Anahtar alt sürece geçmez.** Sandbox ortam temizliği zaten bunu sağlar
   (§3.3); kasa hiçbir zaman `os.environ`'a yazmaz.

`redact()` desen değil **birebir dize** eşleşmesiyle çalışır: anahtarın tam
değeri bilindiği için, sır taramasının desen tabanlı olmasından kaynaklanan
belirsizlik (bilinen sınır S3) kullanıcı anahtarları için geçerli değildir.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from pydantic import SecretStr

from src.transcript.models import Role

MASK = "[ANAHTAR GİZLENDİ]"

# Kısa bir dize ya yanlışlıkla girilmiştir ya da anahtar değildir. Eşiğin
# altındakiler redact() için de tehlikelidir: 4 karakterlik bir "anahtar"
# transkriptteki masum metinleri de silerdi.
MIN_KEY_LENGTH = 20

ENV_VAR_FOR_PROVIDER: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

# Anahtar gerektirmeyen sağlayıcılar
KEYLESS_PROVIDERS = frozenset({"ollama", "replay"})


class KeyRejected(ValueError):
    """Anahtar reddedildi.

    Mesajı ASLA anahtarın kendisini içermez: bu istisna bir HTTP yanıtına
    veya log'a düşebilir.
    """


@dataclass(frozen=True)
class KeyFingerprint:
    """Arayüze dönen tek temsil. Anahtarın kendisini içermez."""

    rol: str
    saglayici: str
    son_dort: str
    uzunluk: int
    kaynak: str  # "arayuz" | "ortam"

    @property
    def maske(self) -> str:
        return f"••••{self.son_dort}"

    def as_dict(self) -> dict[str, object]:
        return {
            "rol": self.rol,
            "saglayici": self.saglayici,
            "maske": self.maske,
            "uzunluk": self.uzunluk,
            "kaynak": self.kaynak,
        }


@dataclass(frozen=True)
class _Entry:
    saglayici: str
    secret: SecretStr


class KeyVault:
    """Bellekte tutulan rol bazlı anahtar kasası."""

    def __init__(self) -> None:
        self._entries: dict[Role, _Entry] = {}

    # -- yazma --------------------------------------------------------------

    def set(self, rol: Role, saglayici: str, anahtar: str) -> KeyFingerprint:
        provider = saglayici.strip().lower()
        if provider in KEYLESS_PROVIDERS:
            raise KeyRejected(f"'{provider}' sağlayıcısı API anahtarı kullanmaz")
        if provider not in ENV_VAR_FOR_PROVIDER:
            raise KeyRejected(f"bilinmeyen sağlayıcı: '{provider}'")

        cleaned = anahtar.strip()
        if len(cleaned) < MIN_KEY_LENGTH:
            # Uzunluk söylenir, değer söylenmez.
            raise KeyRejected(
                f"anahtar çok kısa ({len(cleaned)} karakter, en az {MIN_KEY_LENGTH})"
            )
        if any(ch.isspace() for ch in cleaned):
            raise KeyRejected("anahtar boşluk karakteri içeremez")

        self._entries[rol] = _Entry(provider, SecretStr(cleaned))
        return self._fingerprint(rol, provider, cleaned, "arayuz")

    def clear(self, rol: Role | None = None) -> None:
        if rol is None:
            self._entries.clear()
        else:
            self._entries.pop(rol, None)

    # -- okuma --------------------------------------------------------------

    def get(self, rol: Role, saglayici: str) -> str | None:
        """Ham anahtarı döndürür. YALNIZCA sağlayıcı istemcisini kuran kod çağırır.

        Arayüze giden hiçbir yol bu yöntemi çağırmaz; onlar `fingerprints()`
        kullanır. Arayüzde girilen anahtar ortam değişkenini geçersiz kılar,
        çünkü daha yeni ve daha açık bir niyettir.
        """
        entry = self._entries.get(rol)
        if entry is not None and entry.saglayici == saglayici.strip().lower():
            return entry.secret.get_secret_value()
        env_var = ENV_VAR_FOR_PROVIDER.get(saglayici.strip().lower())
        if env_var:
            value = (os.getenv(env_var) or "").strip()
            return value or None
        return None

    def fingerprints(self) -> list[KeyFingerprint]:
        """Arayüzün görebileceği her şey."""
        result = [
            self._fingerprint(rol, e.saglayici, e.secret.get_secret_value(), "arayuz")
            for rol, e in self._entries.items()
        ]
        result.sort(key=lambda f: f.rol)
        return result

    def has_key_for(self, rol: Role, saglayici: str) -> bool:
        return self.get(rol, saglayici) is not None

    # -- sızıntı önleme -----------------------------------------------------

    def _known_secrets(self) -> list[str]:
        """Kasadaki anahtarlar + ortamdaki anahtarlar.

        Ortamdakiler de dahildir: bir anahtarın .env'den gelmiş olması onu
        transkripte yazılabilir yapmaz.
        """
        secrets = [e.secret.get_secret_value() for e in self._entries.values()]
        for env_var in ENV_VAR_FOR_PROVIDER.values():
            value = (os.getenv(env_var) or "").strip()
            if len(value) >= MIN_KEY_LENGTH:
                secrets.append(value)
        return secrets

    def redact(self, text: str) -> str:
        """Bilinen anahtarları metinden birebir siler.

        Transkripte, log'a veya HTTP yanıtına giden HER metin buradan geçer.
        Desen tahmini yoktur: anahtarın tam değeri bilindiği için eşleşme
        kesindir.
        """
        for secret in self._known_secrets():
            if secret and secret in text:
                text = text.replace(secret, MASK)
        return text

    def contains_secret(self, text: str) -> bool:
        return any(s and s in text for s in self._known_secrets())

    # -- yardımcılar --------------------------------------------------------

    @staticmethod
    def _fingerprint(
        rol: Role, saglayici: str, anahtar: str, kaynak: str
    ) -> KeyFingerprint:
        return KeyFingerprint(
            rol=rol.value,
            saglayici=saglayici,
            son_dort=anahtar[-4:],
            uzunluk=len(anahtar),
            kaynak=kaynak,
        )

    def __repr__(self) -> str:
        """Kasa hiçbir koşulda içeriğini yazdırmaz.

        Varsayılan dataclass/dict repr'ı bir istisna izinde (traceback)
        anahtarları döküyor olurdu.
        """
        return f"<KeyVault rolleri={sorted(r.value for r in self._entries)}>"

    __str__ = __repr__
