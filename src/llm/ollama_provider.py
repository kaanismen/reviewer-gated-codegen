"""Ollama sağlayıcısı — çevrimdışı yedek.

Ollama host makinede çalışır; konteyner `host.docker.internal` üzerinden
erişir (§3.3). Anahtar gerektirmez ve maliyeti sıfırdır, dolayısıyla ağ
veya kota sorununda demo yedeği olarak durur.
"""

from __future__ import annotations

import httpx

from src.llm.provider import (
    LlmProvider,
    LlmRequest,
    LlmResponse,
    ProviderError,
    ProviderUnavailable,
    Redactor,
    Usage,
)


class OllamaProvider(LlmProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        redactor: Redactor | None = None,
        timeout: float = 300.0,
    ) -> None:
        super().__init__(redactor)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def complete(self, request: LlmRequest) -> LlmResponse:
        body = {
            "model": request.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": request.system},
                *({"role": m.rol, "content": m.icerik} for m in request.messages),
            ],
            "options": {"num_predict": request.max_tokens},
        }
        try:
            response = httpx.post(
                f"{self._base_url}/api/chat", json=body, timeout=self._timeout
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(
                f"ollama'ya ulaşılamadı ({self._base_url}): {self.safe(str(exc))}"
            ) from exc

        if response.status_code >= 400:
            raise ProviderError(
                f"ollama hatası ({response.status_code}): {self.safe(response.text)}"
            )

        data = response.json()
        return LlmResponse(
            metin=str((data.get("message") or {}).get("content") or "").strip(),
            # Ollama yereldir; maliyet sıfırdır ama token sayıları yine de
            # kaydedilir — limit denetimi sağlayıcıdan bağımsız çalışmalı.
            kullanim=Usage.priced(
                f"ollama/{request.model}",
                token_girdi=int(data.get("prompt_eval_count") or 0),
                token_cikti=int(data.get("eval_count") or 0),
            ),
            model=str(data.get("model") or request.model),
            saglayici=self.name,
            durdurma_nedeni=str(data.get("done_reason") or ""),
        )

    def available(self) -> bool:
        """Ollama ayakta mı? Sağlık ucu bunu raporlar."""
        try:
            return httpx.get(f"{self._base_url}/api/tags", timeout=2.0).status_code < 400
        except httpx.HTTPError:
            return False
