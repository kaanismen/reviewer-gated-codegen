"""Yollar ve sağlayıcı seçimi — tek doğru kaynak.

Sihirli sabit yasağı (PROJECT.md §11) gereği yol ve sağlayıcı kararları
yalnızca burada verilir. Kontrol limitleri ayrı dosyadadır: orchestrator/limits.py
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

ProviderName = Literal["anthropic", "openai", "ollama", "replay"]
PROVIDER_NAMES: tuple[str, ...] = get_args(ProviderName)

# src/config.py -> src/ -> proje kökü
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
CASSETTES_DIR = PROJECT_ROOT / "tests" / "cassettes"

# Konteynerde /workspaces; hostta geliştirirken proje altındaki dizin.
WORKSPACES_ROOT = Path(os.getenv("WORKSPACES_ROOT") or PROJECT_ROOT / "workspaces")


@dataclass(frozen=True)
class ProviderChoice:
    """Seçilen sağlayıcı ve seçimin gerekçesi.

    Gerekçe arayüzde gösterilir: eğitmen replay modunda olduğunu ve nedenini
    tahmin etmek zorunda kalmamalı.
    """

    name: ProviderName
    reason: str

    @property
    def is_offline(self) -> bool:
        return self.name == "replay"


def _has(var: str) -> bool:
    return bool((os.getenv(var) or "").strip())


def resolve_provider() -> ProviderChoice:
    """Sağlayıcıyı seçer ve ASLA istisna fırlatmaz.

    Anahtarsız çalışabilirlik zorunludur (PROJECT.md §3.3): yanlış veya eksik
    yapılandırma sistemi açılmaz hale getirmemeli, replay moduna düşürmelidir.
    Ancak sessizce düşmez — gerekçe kaydedilir ve arayüzde gösterilir.
    """
    requested = (os.getenv("LLM_PROVIDER") or "").strip().lower()

    if requested and requested not in PROVIDER_NAMES:
        return ProviderChoice(
            "replay",
            f"LLM_PROVIDER='{requested}' tanınmıyor; replay moduna düşüldü.",
        )

    if requested == "anthropic" or (not requested and _has("ANTHROPIC_API_KEY")):
        if _has("ANTHROPIC_API_KEY"):
            return ProviderChoice("anthropic", "ANTHROPIC_API_KEY bulundu.")
        return ProviderChoice(
            "replay", "anthropic istendi ama ANTHROPIC_API_KEY boş; replay moduna düşüldü."
        )

    if requested == "openai" or (not requested and _has("OPENAI_API_KEY")):
        if _has("OPENAI_API_KEY"):
            return ProviderChoice("openai", "OPENAI_API_KEY bulundu.")
        return ProviderChoice(
            "replay", "openai istendi ama OPENAI_API_KEY boş; replay moduna düşüldü."
        )

    if requested == "ollama":
        return ProviderChoice("ollama", f"Ollama isteniyor: {ollama_base_url()}")

    if requested == "replay":
        return ProviderChoice("replay", "replay açıkça istendi.")

    return ProviderChoice(
        "replay", "Hiçbir API anahtarı tanımlı değil; kayıtlı senaryolar oynatılacak."
    )


def ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL") or "http://host.docker.internal:11434"


def in_container() -> bool:
    """Konteyner içinde miyiz? Sandbox katmanları buna göre rapor edilir."""
    return Path("/.dockerenv").exists()
