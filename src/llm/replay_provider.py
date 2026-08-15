"""Kayıt/oynatma sağlayıcısı — PROJECT.md §8.3, §10.

LLM sistemin tek öngörülemez parçasıdır. Kabul testleri onun ruh halini
değil kendi mantığını sınamalı, bu yüzden gerçek çağrılar kasete kaydedilir
ve testlerde geri oynatılır. Sonuç: **API anahtarı olmadan, saniyeler
içinde, deterministik** uçtan uca test.

İki mod:

- **Oynatma** (`inner=None`): kaset yoksa `CassetteMissing` fırlatır.
  Sessizce sahte bir yanıt üretmez — testin neyi kaçırdığı görünmeli.
- **Kayıt** (`inner=<gerçek sağlayıcı>`): kaset yoksa gerçek çağrı yapılır
  ve sonuç yazılır. Kaset yazılmadan önce sır taramasından geçer.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.llm.provider import (
    CassetteMissing,
    LlmProvider,
    LlmRequest,
    LlmResponse,
    ProviderError,
    Redactor,
)
from src.security import secret_scan
from src.security.input_guard import DELIMITER_CLOSE, DELIMITER_OPEN


class ReplayProvider(LlmProvider):
    name = "replay"

    def __init__(
        self,
        cassettes_dir: Path,
        inner: LlmProvider | None = None,
        redactor: Redactor | None = None,
    ) -> None:
        super().__init__(redactor)
        self.cassettes_dir = Path(cassettes_dir)
        self.inner = inner

    @property
    def recording(self) -> bool:
        return self.inner is not None

    def path_for(self, request: LlmRequest) -> Path:
        return self.cassettes_dir / f"{request.fingerprint()}.json"

    def count(self) -> int:
        if not self.cassettes_dir.is_dir():
            return 0
        return len(list(self.cassettes_dir.glob("*.json")))

    def recorded_tasks(self) -> list[str]:
        """Kasetlerden oynatılabilir görev metinlerini çıkarır.

        Anahtarsız modda kullanıcı hangi görevin kayıtlı olduğunu bilemez;
        rastgele bir metin yazarsa `CassetteMissing` alır. Bu, "anahtarsız
        çalışabilirlik" iddiasını kullanıcı için bir tuzağa çevirir.
        Planlayıcı kasetlerindeki veri bloğu görev metnini taşır.
        """
        if not self.cassettes_dir.is_dir():
            return []
        tasks: set[str] = set()
        for path in self.cassettes_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for message in (data.get("istek") or {}).get("messages") or []:
                metin = str(message.get("icerik") or "")
                if DELIMITER_OPEN in metin and DELIMITER_CLOSE in metin:
                    gorev = metin.split(DELIMITER_OPEN, 1)[1].split(DELIMITER_CLOSE, 1)[0]
                    if gorev.strip():
                        tasks.add(gorev.strip())
        return sorted(tasks)

    def complete(self, request: LlmRequest) -> LlmResponse:
        path = self.path_for(request)
        if path.is_file():
            return self._load(path)

        if self.inner is None:
            raise CassetteMissing(
                f"kaset yok: {path.name} (model={request.model}, "
                f"{len(request.messages)} mesaj). Kayıt için LLM_KAYIT=1 ile "
                f"gerçek bir sağlayıcı üzerinden çalıştırın."
            )

        response = self.inner.complete(request)
        self._save(path, request, response)
        return response

    # -- kaset G/Ç ----------------------------------------------------------

    def _load(self, path: Path) -> LlmResponse:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ProviderError(f"kaset okunamadı ({path.name}): {exc}") from exc
        return LlmResponse.from_dict(data.get("yanit") or {})

    def _save(self, path: Path, request: LlmRequest, response: LlmResponse) -> None:
        """Kaseti diske yazar; önce sırdan arındırır.

        Kasetler depoya commit edilir (§8.3). Gerçek bir çağrının yanıtında
        veya hata metninde sır bulunması ihtimaline karşı hem gizleme
        uygulanır hem de kalan bir bulgu varsa kayıt **yapılmaz** — bir
        testi kolaylaştırmak için sır commit etmek kabul edilebilir bir
        takas değildir.
        """
        cleaned_text = secret_scan.redact(self._redact(response.metin))
        payload = {
            "parmak_izi": request.fingerprint(),
            "kayit_zamani": datetime.now(timezone.utc).isoformat(),
            "istek": request.canonical(),
            "yanit": {**response.as_dict(), "metin": cleaned_text},
        }
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)

        findings = secret_scan.scan(serialized)
        if findings:
            raise ProviderError(
                "kaset yazılmadı: sır taraması bulgu verdi "
                f"({', '.join(sorted({f.tur for f in findings}))})"
            )

        self.cassettes_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(serialized, encoding="utf-8")
