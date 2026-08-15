"""OpenAI sağlayıcısı — belgelenmiş REST ucu üzerinden.

**Neden SDK değil:** bu projeden OpenAI'a yapılan tek çağrı şekli var
(sistem promptu + mesaj listesi → metin). Tek bir çağrı için büyük bir
istemci bağımlılığı taşımak, imaj boyutu ve sürüm sürüklenmesi açısından
karşılığını vermiyor. `/v1/chat/completions` uzun süredir kararlı bir
sözleşme; `httpx` zaten bağımlılık listesinde.

Anthropic tarafında tersi geçerlidir: orada akış, prompt önbelleği ve
düşünme blokları gibi SDK'nın kendi soyutlamaları kullanılıyor.
"""

from __future__ import annotations

import httpx

from src.llm.provider import (
    LlmProvider,
    LlmRequest,
    LlmResponse,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimited,
    ProviderUnavailable,
    Redactor,
    Usage,
)

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider(LlmProvider):
    name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        redactor: Redactor | None = None,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(redactor)
        if not api_key:
            raise ProviderAuthError("openai sağlayıcısı için API anahtarı yok")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def complete(self, request: LlmRequest) -> LlmResponse:
        payload = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system},
                *({"role": m.rol, "content": m.icerik} for m in request.messages),
            ],
        }
        data = self._post(payload, request.max_tokens)

        choice = (data.get("choices") or [{}])[0]
        usage = data.get("usage") or {}
        return LlmResponse(
            metin=str((choice.get("message") or {}).get("content") or "").strip(),
            kullanim=Usage.priced(
                request.model,
                token_girdi=int(usage.get("prompt_tokens") or 0),
                token_cikti=int(usage.get("completion_tokens") or 0),
            ),
            model=str(data.get("model") or request.model),
            saglayici=self.name,
            durdurma_nedeni=str(choice.get("finish_reason") or ""),
        )

    def _post(self, payload: dict, max_tokens: int) -> dict:
        """İsteği gönderir; token alanı adı için tek seferlik uyum denemesi yapar.

        Yeni modeller `max_completion_tokens`, eski modeller `max_tokens`
        bekliyor. Hangisinin geçerli olduğu model kimliğinden anlaşılamadığı
        için önce yenisi denenir; sunucu alanı reddederse eskisiyle bir kez
        tekrar denenir. Sessizce limitsiz göndermek seçenek değil — çıktı
        tavanı bir maliyet kontrolüdür.
        """
        for field in ("max_completion_tokens", "max_tokens"):
            body = {**payload, field: max_tokens}
            try:
                response = httpx.post(
                    f"{self._base_url}/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=self._timeout,
                )
            except httpx.HTTPError as exc:
                raise ProviderUnavailable(
                    f"openai bağlantı hatası: {self.safe(str(exc))}"
                ) from exc

            if response.status_code == 400 and field == "max_completion_tokens":
                if "max_completion_tokens" in response.text:
                    continue  # eski alan adıyla tekrar dene
            self._raise_for_status(response)
            return response.json()

        raise ProviderError("openai isteği hiçbir token alanı adıyla kabul edilmedi")

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        detail = self.safe(response.text)
        if response.status_code in (401, 403):
            raise ProviderAuthError(f"openai kimlik doğrulama hatası: {detail}")
        if response.status_code == 429:
            raise ProviderRateLimited(f"openai hız sınırı: {detail}")
        if response.status_code >= 500:
            raise ProviderUnavailable(f"openai sunucu hatası ({response.status_code}): {detail}")
        raise ProviderError(f"openai API hatası ({response.status_code}): {detail}")
