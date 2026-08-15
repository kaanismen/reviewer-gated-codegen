"""Rol → sağlayıcı eşlemesi — PROJECT.md §8.1.

Her agent kendi sağlayıcısını ve modelini kullanabilir: planlayıcı
Anthropic, uygulayıcı OpenAI gibi karışık kurulumlar mümkündür. Karar
sırası şudur:

1. Role özel ortam değişkeni (`LLM_PROVIDER_PLANLAYICI`)
2. Genel ortam değişkeni (`LLM_PROVIDER`)
3. Kasada veya ortamda anahtarı olan sağlayıcı
4. Hiçbiri yoksa `replay`

**Kurulum hatası sistemi açılmaz yapmaz.** Seçilen sağlayıcının anahtarı
yoksa `replay`e düşülür ve gerekçe kaydedilir; arayüz bunu gösterir.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.config import CASSETTES_DIR, ollama_base_url
from src.llm.anthropic_provider import AnthropicProvider
from src.llm.ollama_provider import OllamaProvider
from src.llm.openai_provider import OpenAIProvider
from src.llm.provider import DEFAULT_MAX_TOKENS, LlmProvider, ProviderError
from src.llm.replay_provider import ReplayProvider
from src.security.key_vault import KEYLESS_PROVIDERS, KeyVault
from src.transcript.models import Role

# §8.1 rol–model eşlemesi
ROLE_DEFAULT_MODEL: dict[Role, str] = {
    Role.PLANLAYICI: "claude-opus-5",
    Role.UYGULAYICI: "claude-sonnet-5",
    Role.DENETLEYICI: "claude-opus-5",
}

# Uygulayıcı üç dosyanın tam içeriğini üretir; diğer roller JSON döner.
ROLE_MAX_TOKENS: dict[Role, int] = {
    Role.PLANLAYICI: DEFAULT_MAX_TOKENS,
    Role.UYGULAYICI: 32_000,
    Role.DENETLEYICI: DEFAULT_MAX_TOKENS,
}

KNOWN_PROVIDERS = frozenset({"anthropic", "openai", "ollama", "replay"})
OLLAMA_DEFAULT_MODEL = "llama3.1"


@dataclass(frozen=True)
class RoleConfig:
    rol: Role
    saglayici: str
    model: str
    max_tokens: int
    gerekce: str

    def as_dict(self) -> dict[str, object]:
        return {
            "rol": self.rol.value,
            "saglayici": self.saglayici,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "gerekce": self.gerekce,
        }


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _requested_provider(rol: Role) -> str:
    return (
        _env(f"LLM_PROVIDER_{rol.value.upper()}") or _env("LLM_PROVIDER")
    ).lower()


def resolve_role(rol: Role, vault: KeyVault) -> RoleConfig:
    """Bir rolün hangi sağlayıcı ve modelle çalışacağını belirler."""
    requested = _requested_provider(rol)

    if requested and requested not in KNOWN_PROVIDERS:
        return _replay_config(rol, f"'{requested}' tanınmayan bir sağlayıcı")

    if requested in KEYLESS_PROVIDERS:
        return _keyless_config(rol, requested)

    if requested:
        if vault.has_key_for(rol, requested):
            return _keyed_config(rol, requested, f"{requested} anahtarı mevcut")
        return _replay_config(
            rol, f"{requested} istendi ama {rol.value} için anahtar yok"
        )

    # İstek yoksa: anahtarı olan ilk sağlayıcı
    for candidate in ("anthropic", "openai"):
        if vault.has_key_for(rol, candidate):
            return _keyed_config(rol, candidate, f"{candidate} anahtarı bulundu")

    return _replay_config(rol, "hiçbir API anahtarı tanımlı değil")


def _model_for(rol: Role, default: str) -> str:
    return _env(f"MODEL_{rol.value.upper()}") or default


def _keyed_config(rol: Role, saglayici: str, gerekce: str) -> RoleConfig:
    return RoleConfig(
        rol=rol,
        saglayici=saglayici,
        model=_model_for(rol, ROLE_DEFAULT_MODEL[rol]),
        max_tokens=ROLE_MAX_TOKENS[rol],
        gerekce=gerekce,
    )


def _keyless_config(rol: Role, saglayici: str) -> RoleConfig:
    if saglayici == "ollama":
        return RoleConfig(
            rol=rol,
            saglayici="ollama",
            model=_model_for(rol, OLLAMA_DEFAULT_MODEL),
            max_tokens=ROLE_MAX_TOKENS[rol],
            gerekce=f"ollama isteniyor ({ollama_base_url()})",
        )
    return _replay_config(rol, "replay açıkça istendi")


def _replay_config(rol: Role, gerekce: str) -> RoleConfig:
    return RoleConfig(
        rol=rol,
        saglayici="replay",
        model=_model_for(rol, ROLE_DEFAULT_MODEL[rol]),
        max_tokens=ROLE_MAX_TOKENS[rol],
        gerekce=f"{gerekce}; kayıtlı senaryolar oynatılacak",
    )


def recording_enabled() -> bool:
    """Gerçek çağrılar kasede yazılsın mı?"""
    return _env("LLM_KAYIT") in ("1", "true", "evet")


def build_provider(
    rol: Role, vault: KeyVault, config: RoleConfig | None = None
) -> LlmProvider:
    """Rol için sağlayıcıyı kurar.

    Hata mesajlarının gizlenmesi burada bağlanır: her sağlayıcı kasanın
    `redact` işlevini alır, böylece bir istisna metni anahtar taşıyamaz.
    """
    config = config or resolve_role(rol, vault)
    redactor = vault.redact

    if config.saglayici == "replay":
        return ReplayProvider(CASSETTES_DIR, redactor=redactor)

    if config.saglayici == "ollama":
        provider: LlmProvider = OllamaProvider(ollama_base_url(), redactor=redactor)
    else:
        key = vault.get(rol, config.saglayici)
        if not key:
            raise ProviderError(
                f"{rol.value} için {config.saglayici} anahtarı bulunamadı"
            )
        if config.saglayici == "anthropic":
            provider = AnthropicProvider(key, redactor=redactor)
        elif config.saglayici == "openai":
            provider = OpenAIProvider(key, redactor=redactor)
        else:  # pragma: no cover - KNOWN_PROVIDERS ile kapalı
            raise ProviderError(f"bilinmeyen sağlayıcı: {config.saglayici}")

    if recording_enabled():
        # Kayıt modu: kaset varsa oynatılır, yoksa gerçek çağrı yapılıp yazılır.
        return ReplayProvider(CASSETTES_DIR, inner=provider, redactor=redactor)
    return provider


def all_roles(vault: KeyVault) -> list[RoleConfig]:
    """Üç agent rolünün etkin yapılandırması — sağlık ucu için."""
    return [resolve_role(rol, vault) for rol in ROLE_DEFAULT_MODEL]
