"""Agent tabanı — prompt yükleme, JSON çıkarma, mesaj üretme.

Üç agent aynı iskeleti paylaşır: sürümlü bir prompt dosyası yükle, sağlayıcıyı
çağır, dönen metinden yapısal içeriği çıkar, transkript mesajı üret.

İki kural burada yaşıyor:

1. **Prompt hash'i her mesajda taşınır** (§9). Bir çıktının hangi talimattan
   geldiği sonradan kanıtlanabilir olmalı.
2. **Serbest metin karar sayılmaz** (§6/T4). Çıkarma başarısızsa istisna
   fırlatılır; "muhtemelen kabul etmiştir" gibi bir yorum yapılmaz.
"""

from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from src.config import PROMPTS_DIR
from src.llm.factory import RoleConfig
from src.llm.provider import LlmProvider, LlmRequest, LlmResponse, Message
from src.transcript.models import AgentMessage, Role

# Prompt dosyası adı: <ad>.v<n>.md
_VERSION_RE = re.compile(r"\.v(\d+)$")

PROMPT_BASENAME: dict[Role, str] = {
    Role.PLANLAYICI: "planner",
    Role.UYGULAYICI: "implementer",
    Role.DENETLEYICI: "reviewer",
}


class PromptMissing(RuntimeError):
    """Prompt dosyası yok. Kural K4 gereği bunu AI değil insan yazar."""


class AgentOutputError(RuntimeError):
    """Agent çıktısı yapısal içeriğe dönüştürülemedi.

    `ham` alanı gizlemeden geçmiş ve kısaltılmış çıktıyı taşır; denetleyiciye
    ve transkripte gider ki hatanın ne olduğu görünsün.
    """

    def __init__(self, mesaj: str, ham: str = "") -> None:
        super().__init__(mesaj)
        self.ham = ham


@dataclass(frozen=True)
class LoadedPrompt:
    surum: str  # "planner.v1"
    hash: str  # sha256'nın ilk 12 hanesi
    metin: str


def load_prompt(rol: Role, prompts_dir: Path | None = None) -> LoadedPrompt:
    """Rolün EN YÜKSEK sürümlü promptunu yükler.

    Sürüm dosyaları silinmez (§9); `v2` eklendiğinde `v1` yerinde kalır ve
    yükleyici otomatik olarak yenisine geçer. Böylece prompt iterasyonu
    kodda hiçbir değişiklik gerektirmez.
    """
    directory = Path(prompts_dir or PROMPTS_DIR)
    basename = PROMPT_BASENAME[rol]
    candidates = sorted(
        directory.glob(f"{basename}.v*.md"),
        key=lambda p: int(_VERSION_RE.search(p.stem).group(1))
        if _VERSION_RE.search(p.stem)
        else 0,
    )
    if not candidates:
        raise PromptMissing(
            f"{basename}.v1.md bulunamadı ({directory}). "
            f"Prompt'lar insan tarafından yazılır (kural K4)."
        )
    path = candidates[-1]
    text = path.read_text(encoding="utf-8")
    return LoadedPrompt(
        surum=path.stem,
        hash=hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
        metin=text,
    )


def extract_json(text: str) -> dict:
    """LLM metninden ilk dengeli JSON nesnesini çıkarır.

    Modeller talimata rağmen çıktıyı ``` bloklarına sarabiliyor veya önüne
    bir cümle ekleyebiliyor. Tolere edilen budur — **anlam çıkarımı değil.**
    Dengeli bir nesne bulunamazsa istisna fırlatılır; metnin içinde geçen
    kelimelere bakılıp karar uydurulmaz.
    """
    if not text or not text.strip():
        raise AgentOutputError("agent boş yanıt döndürdü", "")

    stripped = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())

    start = stripped.find("{")
    if start == -1:
        raise AgentOutputError("yanıtta JSON nesnesi yok", stripped[:400])

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(stripped)):
        char = stripped[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start : index + 1]
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError as exc:
                    raise AgentOutputError(
                        f"JSON ayrıştırılamadı: {exc}", candidate[:400]
                    ) from exc
                if not isinstance(parsed, dict):
                    raise AgentOutputError("JSON nesnesi bekleniyordu", candidate[:400])
                return parsed

    raise AgentOutputError("JSON nesnesi kapanmamış", stripped[:400])


@dataclass
class GeneratedOutput:
    """Ayrıştırılmış agent çıktısı — henüz transkript mesajı değil."""

    icerik: BaseModel
    response: LlmResponse
    ham_metin: str


@dataclass
class AgentResult:
    message: AgentMessage
    icerik: BaseModel
    ham_metin: str


class Agent(ABC):
    rol: Role

    def __init__(
        self,
        provider: LlmProvider,
        config: RoleConfig,
        prompt: LoadedPrompt | None = None,
    ) -> None:
        self.provider = provider
        self.config = config
        self.prompt = prompt or load_prompt(self.rol)

    @property
    @abstractmethod
    def content_model(self) -> type[BaseModel]:
        """Bu rolün ürettiği yapısal çıktının şeması.

        Planlayıcı ve denetleyici için bu doğrudan transkript şemasıdır
        (§7.2, §7.4). Uygulayıcı için farklıdır: LLM dosya İÇERİKLERİ
        döndürür, transkripte yazılan kayıt ise dosyalar yazıldıktan sonra
        üretilir (§7.3). Bu yüzden üretim ve mesaj kurma ayrılmıştır.
        """

    def generate(self, messages: list[Message]) -> GeneratedOutput:
        response = self.provider.complete(
            LlmRequest(
                system=self.prompt.metin,
                messages=tuple(messages),
                model=self.config.model,
                max_tokens=self.config.max_tokens,
            )
        )

        payload = extract_json(response.metin)
        try:
            icerik = self.content_model.model_validate(payload)
        except ValidationError as exc:
            raise AgentOutputError(
                f"{self.rol.value} çıktısı şemaya uymuyor: {_first_errors(exc)}",
                json.dumps(payload, ensure_ascii=False)[:400],
            ) from exc
        return GeneratedOutput(icerik=icerik, response=response, ham_metin=response.metin)

    def build_message(self, icerik, response: LlmResponse, tur: int) -> AgentMessage:
        """Köken bilgisini bağlar: prompt sürümü, hash, model, token, maliyet."""
        return AgentMessage(
            tur=tur,
            rol=self.rol,
            icerik=icerik,
            prompt_surumu=self.prompt.surum,
            prompt_hash=self.prompt.hash,
            model=response.model,
            token_girdi=response.kullanim.token_girdi,
            token_cikti=response.kullanim.token_cikti,
            maliyet_usd=response.kullanim.maliyet_usd,
        )

    def run(self, messages: list[Message], tur: int) -> AgentResult:
        """Üretim + mesaj kurma. Çıktısı doğrudan transkript şeması olan
        roller (planlayıcı, denetleyici) bunu kullanır."""
        generated = self.generate(messages)
        return AgentResult(
            message=self.build_message(generated.icerik, generated.response, tur),
            icerik=generated.icerik,
            ham_metin=generated.ham_metin,
        )


def _first_errors(exc: ValidationError, limit: int = 3) -> str:
    """Doğrulama hatalarını modele geri verilebilecek kadar kısa özetler."""
    parts = []
    for error in exc.errors()[:limit]:
        konum = ".".join(str(p) for p in error.get("loc", ())) or "(kök)"
        parts.append(f"{konum}: {error.get('msg')}")
    return "; ".join(parts)
