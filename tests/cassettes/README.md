# tests/cassettes/

Kaydedilmiş LLM istek–yanıt çiftleri. Dosya adı isteğin parmak izidir
(`LlmRequest.fingerprint()` — model, max_tokens, sistem promptu hash'i ve
mesaj listesinden türetilir).

## Neden var

LLM sistemin tek öngörülemez parçası. Kabul testleri onun o günkü ruh
halini değil sistemin kendi mantığını sınamalı. Kasetler sayesinde uçtan
uca testler **API anahtarı olmadan, saniyeler içinde, deterministik**
çalışır.

Ayrıca `.env` boşken sistem `replay` moduyla açılır ve bu kasetleri
oynatır — eğitmen hiçbir anahtar girmeden sistemi çalışırken görebilir.

## Kayıt

```bash
LLM_KAYIT=1 docker compose up
```

Kaset varsa oynatılır, yoksa gerçek çağrı yapılır ve sonuç buraya yazılır.

## Güvenlik

Kasetler depoya commit edilir. Yazılmadan önce **sır taramasından geçerler**;
bir bulgu kalırsa kaset yazılmaz. Bir testi kolaylaştırmak için sır commit
etmek kabul edilebilir bir takas değildir.

Sistem promptunun tam metni kasete yazılmaz, yalnızca hash'i: prompt
dosyaları zaten `prompts/` altında sürümlü duruyor.
