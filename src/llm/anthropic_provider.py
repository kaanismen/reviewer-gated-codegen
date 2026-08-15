"""Anthropic (Claude) sağlayıcısı.

Resmî `anthropic` SDK'sı kullanılır. Üç tasarım tercihi:

- **Akış (streaming).** Uygulayıcı üç dosyanın tam içeriğini üretir; uzun
  çıktıda tek seferlik istek zaman aşımına girebilir. `messages.stream()`
  bağlam yöneticisi kullanılıp `get_final_message()` ile tam yanıt alınır.
- **Prompt önbelleği.** Sistem promptu rol başına sabittir ve her turda
  yeniden gönderilir; `cache_control` ile önbelleğe alınır. Önbellek
  token'ları maliyet hesabına ayrı katsayılarla girer (`pricing`).
- **Uyarlanabilir düşünme.** Opus 5'te düşünme varsayılan olarak açıktır;
  `{"type": "adaptive"}` açıkça yazılır ki davranış modelden bağımsız olsun.
  `budget_tokens` Opus 5'te 400 döndürür, kullanılmaz.
"""

from __future__ import annotations

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


class AnthropicProvider(LlmProvider):
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        redactor: Redactor | None = None,
        timeout: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        super().__init__(redactor)
        if not api_key:
            raise ProviderAuthError("anthropic sağlayıcısı için API anahtarı yok")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - imajda kurulu
            raise ProviderUnavailable(f"anthropic SDK yüklenemedi: {exc}") from exc

        self._sdk = anthropic
        self._client = anthropic.Anthropic(
            api_key=api_key, timeout=timeout, max_retries=max_retries
        )

    def complete(self, request: LlmRequest) -> LlmResponse:
        sdk = self._sdk
        try:
            with self._client.messages.stream(
                model=request.model,
                max_tokens=request.max_tokens,
                # Liste biçimi cache_control taşıyabilmek için gerekli.
                system=[
                    {
                        "type": "text",
                        "text": request.system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": m.rol, "content": m.icerik} for m in request.messages],
                thinking={"type": "adaptive"},
            ) as stream:
                message = stream.get_final_message()
        except sdk.AuthenticationError as exc:
            raise ProviderAuthError(
                f"anthropic kimlik doğrulama hatası: {self.safe(str(exc))}"
            ) from exc
        except sdk.PermissionDeniedError as exc:
            raise ProviderAuthError(
                f"anthropic yetki hatası: {self.safe(str(exc))}"
            ) from exc
        except sdk.RateLimitError as exc:
            raise ProviderRateLimited(
                f"anthropic hız sınırı: {self.safe(str(exc))}"
            ) from exc
        except sdk.APIConnectionError as exc:
            raise ProviderUnavailable(
                f"anthropic bağlantı hatası: {self.safe(str(exc))}"
            ) from exc
        except sdk.APIStatusError as exc:
            raise ProviderError(
                f"anthropic API hatası ({exc.status_code}): {self.safe(str(exc))}"
            ) from exc

        return LlmResponse(
            metin=_text_of(message),
            kullanim=Usage.priced(
                request.model,
                token_girdi=getattr(message.usage, "input_tokens", 0) or 0,
                token_cikti=getattr(message.usage, "output_tokens", 0) or 0,
                onbellek_yazma=getattr(message.usage, "cache_creation_input_tokens", 0) or 0,
                onbellek_okuma=getattr(message.usage, "cache_read_input_tokens", 0) or 0,
            ),
            model=getattr(message, "model", request.model),
            saglayici=self.name,
            durdurma_nedeni=getattr(message, "stop_reason", "") or "",
        )


def _text_of(message) -> str:
    """Yanıttan yalnızca metin bloklarını toplar.

    Düşünme açıkken içerik listesi `thinking` blokları da taşır; bunlar
    ayrıştırılacak JSON'un parçası değildir ve dışarıda bırakılmalıdır.
    """
    parts = [
        block.text
        for block in getattr(message, "content", [])
        if getattr(block, "type", "") == "text"
    ]
    return "".join(parts).strip()
