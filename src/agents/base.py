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

    `kesildi` ayrı tutulur: token tavanına takılmış bir yanıt ile şemayı
    yanlış anlamış bir yanıt farklı sorunlardır ve farklı çözülürler.
    """

    def __init__(self, mesaj: str, ham: str = "", kesildi: bool = False) -> None:
        super().__init__(mesaj)
        self.ham = ham
        self.kesildi = kesildi


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


def repair_json(text: str) -> str:
    """LLM'lerin en sık yaptığı iki JSON hatasını onarır.

    1. **Dize içinde kaçışlanmamış satır sonu / sekme.** Model kodu JSON
       dizesine gömerken gerçek satır sonu bırakır; `json` bunu reddeder.
    2. **Kapanıştan önce fazladan virgül** (`[1, 2,]`).

    Onarım yalnızca **katı ayrıştırma başarısız olduktan sonra** denenir ve
    tek geçişte, dize içinde olup olmadığını izleyerek yapılır — kör bir
    düzenli ifade, dizenin içindeki masum metni de bozardı.

    Bilinçli olarak yapılmayanlar: tırnak türü değiştirme, yorum satırı
    silme, eksik parantez tamamlama. Bunlar tahmin gerektirir ve yanlış
    tahmin, bozuk çıktıyı sessizce "geçerli" hale getirir.
    """
    KACIS = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
    out: list[str] = []
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            elif char in KACIS:
                out.append(KACIS[char])
                continue
            out.append(char)
            continue

        if char == '"':
            in_string = True
            out.append(char)
            continue

        if char == ",":
            # Sonraki boşluk dışı karakter kapanışsa virgül fazladır.
            sonraki = next(
                (c for c in text[index + 1:] if not c.isspace()), ""
            )
            if sonraki in "}]":
                continue
        out.append(char)

    return "".join(out)


def extract_json(text: str) -> tuple[dict, bool]:
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
                onarildi = False
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    try:
                        parsed = json.loads(repair_json(candidate))
                        onarildi = True
                    except json.JSONDecodeError as exc:
                        raise AgentOutputError(
                            f"JSON ayrıştırılamadı (onarım da işe yaramadı): {exc}",
                            candidate[:400],
                        ) from exc
                if not isinstance(parsed, dict):
                    raise AgentOutputError("JSON nesnesi bekleniyordu", candidate[:400])
                return parsed, onarildi

    raise AgentOutputError("JSON nesnesi kapanmamış", stripped[:400])


@dataclass
class GeneratedOutput:
    """Ayrıştırılmış agent çıktısı — henüz transkript mesajı değil."""

    icerik: BaseModel
    response: LlmResponse
    ham_metin: str
    # JSON katı ayrıştırmadan geçmedi, onarılarak okundu. Transkripte
    # yazılır: sessizce onarmak, çıktı kalitesini gizlemek olurdu.
    onarildi: bool = False


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

    def generate(
        self, messages: list[Message], max_tokens: int | None = None
    ) -> GeneratedOutput:
        response = self.provider.complete(
            LlmRequest(
                system=self.prompt.metin,
                messages=tuple(messages),
                model=self.config.model,
                max_tokens=max_tokens or self.config.max_tokens,
            )
        )

        # Kesilme JSON ayrıştırmasından ÖNCE kontrol edilir. Aksi hâlde
        # yarıda kalmış bir yanıt "JSON kapanmamış" diye raporlanır ve hata
        # bütçe sorunu değil, modelin şemayı anlamaması gibi görünür.
        if response.kesildi:
            raise AgentOutputError(
                f"{self.rol.value} çıktısı token tavanına takıldı ve yarıda "
                f"kesildi (durdurma nedeni: {response.durdurma_nedeni}, "
                f"tavan: {max_tokens or self.config.max_tokens}, "
                f"üretilen: {response.kullanim.token_cikti})",
                response.metin[-300:],
                kesildi=True,
            )

        try:
            payload, onarildi = extract_json(response.metin)
        except AgentOutputError as exc:
            # Durdurma nedeni tanı için kritik: "kesildi" ile "bozuk JSON
            # üretti" farklı sorunlardır ve mesaja yazılmazsa ayırt edilemez.
            raise AgentOutputError(
                f"{exc} [durdurma_nedeni={response.durdurma_nedeni or 'bildirilmedi'}, "
                f"çıktı={response.kullanim.token_cikti} tok]",
                exc.ham,
            ) from exc

        try:
            icerik = self.content_model.model_validate(payload)
        except ValidationError as exc:
            raise AgentOutputError(
                f"{self.rol.value} çıktısı şemaya uymuyor: {_first_errors(exc)}",
                json.dumps(payload, ensure_ascii=False)[:400],
            ) from exc
        return GeneratedOutput(
            icerik=icerik,
            response=response,
            ham_metin=response.metin,
            onarildi=onarildi,
        )

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
