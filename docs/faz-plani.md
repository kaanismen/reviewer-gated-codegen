# Faz Planı — Agent Oyun Atölyesi

> Bu dosya **nasıl inşa edileceğini** anlatır. *Ne* inşa edileceği `PROJECT.md`'de tanımlıdır.
>
> **Sürüm:** 1.0 · **Tarih:** 14 Ağustos 2026 · **Süre:** 3 gün (14–16 Ağustos)

---

## 1. Mimari analiz

### 1.1 Bağımlılık grafı

`PROJECT.md` §3.1'deki katman kuralı (`web → orchestrator → agents → {llm, tools} → sandbox`) *çalışma anı* bağımlılığıdır. İnşa sırası bundan farklıdır, çünkü inşa sırasını belirleyen şey **bir modülün test edilebilmesi için başka neyin var olması gerektiğidir.**

```
  config.py ── limits.py ── transcript/models.py        ← hiçbir şeye bağlı değil
       │            │              │
       │            └──────┬───────┘
       │                   ▼
       │            state_machine.py                    ← saf; LLM yok, disk yok
       │                   │
       ├────► security/ ───┤                            ← saf; bağımsız test edilir
       │      sandbox/     │
       │         │         │
       │         ▼         │
       │   tools/test_runner.py                         ← sandbox'a bağlı
       │         │         │
       │    llm/provider.py + replay_provider           ← saf arayüz
       │         │         │
       │         └────┬────┘
       │              ▼
       │        agents/ ── prompts/*.md   ← İNSAN KAPISI (kural K4)
       │              │
       │              ▼
       │      orchestrator/loop.py                      ← her şeyi birleştirir
       │              │
       └──────────────┴────► web/app.py                 ← en son
```

### 1.2 Sıralamayı belirleyen üç ilke

**(a) Deterministik olan, olmayandan önce gelir.**
LLM çağrısı sistemin tek öngörülemez parçası. Durum makinesini agent'lardan sonra yazarsak, her durum makinesi testi aslında LLM'in o günkü ruh halini test eder — hata bulunduğunda kusurun makinede mi modelde mi olduğu ayırt edilemez. Bu yüzden `state_machine.py`, `limits.py`, `security/` ve `sandbox/` — hepsi LLM'e hiç dokunmadan yazılıp test edilir. Rubrikteki **güvenlik ve test** kaleminin tamamı bu deterministik bölgede kazanılır.

**(b) En riskli varsayım, en ucuza test edilir.**
Sıradaki üç varsayım henüz kanıtlanmadı ve üçü de geç keşfedilirse pahalıdır:

| Varsayım | Nerede test edilir | Geç keşfedilirse maliyeti |
|---|---|---|
| Eğitmenin makinesinde `docker compose up` çalışır | **Faz 0** — boş bir sayfayla, bugün | Çok yüksek: teslim edilemez ürün |
| rlimit'ler Docker Desktop (WSL2) altında fiilen uygulanır | **Faz 2** — doğrudan ölçümle | Yüksek: güvenlik iddiaları kanıtsız kalır |
| LLM 5 tur içinde çalışan bir oyun üretebilir | **Faz 4** — tic-tac-toe ile | Orta: kapsam daraltılarak telafi edilebilir |

İlk ikisi AI günlüğündeki denetim tablosunda **"doğrulanmadı"** olarak işaretli. Faz 0 ve Faz 2 bu satırları kapatmak için var.

**(c) Kanıt, kanıtı anlatan belgeden önce gelir.**
`docs/teknik.md` "rlimit'ler şu şekilde uygulanıyor" diye yazacaksa, o ölçüm önce yapılmış olmalı. Belgeleri fazların sonuna koymak üslup tercihi değil; henüz ölçülmemiş bir şeyi ölçülmüş gibi yazmama kararıdır. Denetim tablosunda zaten bu türden bir hata kayıtlı (bkz. `ai-gunlugu.md`, Kayıt 1.7).

### 1.3 Kritik yol ve paralellik

**Kritik yol:** Faz 0 → Faz 1 → Faz 3 → Faz 4 → Faz 5.
**Kritik yol dışı:** Faz 2 (güvenlik + sandbox) yalnızca Faz 4'ün denetleyicisinden önce bitmek zorunda; Faz 1 ve 3 ile sırası değişebilir.

**İnsan kapısı — Faz 4'ün gerçek ön koşulu.** Eğitim kuralı K4 gereği `prompts/planner.v1.md`, `implementer.v1.md`, `reviewer.v1.md` **insan tarafından yazılır.** Bunlar Faz 4'ün girdisidir; Faz 4 başladığında hazır değillerse kritik yol durur. Bu yüzden prompt yazımı Faz 2–3 sürerken paralel yürümelidir — kritik yolun üstüne oturtulmamalıdır.

---

## 2. Fazlar

### Faz 0 — İskelet ve dockerize çalışma · *~1 saat*

| | |
|---|---|
| **Amaç** | En yeni ve en test edilmemiş şartı (K5) bugün kanıtlamak |
| **Üretilenler** | `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.gitignore`, `.env.example`, `requirements.txt`, `src/config.py`, `src/orchestrator/limits.py`, `src/web/app.py`, `src/web/static/index.html`, `README.md` |
| **Tamamlanma** | Temiz kabuktan `docker compose up` → `localhost:8000` açılıyor · konteynerde `node --version` = v20.x · `runner` kullanıcısı mevcut · `.env` **yokken** hata vermiyor · imaj < 500 MB |

### Faz 1 — Sözleşmeler ve durum makinesi · *~2 saat*

| | |
|---|---|
| **Amaç** | Sistemin iskeletini LLM'e hiç dokunmadan çalışır ve test edilir hale getirmek |
| **Üretilenler** | `transcript/models.py` (§7 şemaları, pydantic) · `transcript/store.py` · `orchestrator/state_machine.py` (G1–G13) · `tests/test_state_machine.py` · `tests/test_limits.py` |
| **Tamamlanma** | 13 geçişin her biri için test · her koruma koşulunun hem geçen hem düşen hali · `KK-02` ve `KK-03` (tur limiti, ilerleme-yok) geçiyor · **sıfır LLM çağrısı** |

### Faz 2 — Sandbox ve güvenlik · *~3 saat*

| | |
|---|---|
| **Amaç** | Rubriğin güvenlik-test kalemini kanıtla kapatmak; denetleyicinin muhtaç olduğu test koşucusunu üretmek |
| **Üretilenler** | `security/{path_guard,secret_scan,input_guard}.py` · `sandbox/{import_guard,rlimits,process_runner}.py` · `tools/test_runner.py` · `tests/test_security.py` |
| **Tamamlanma** | T1, T2, T2b, T3, T5, T6, T7 için birer geçen negatif test · **rlimit'lerin fiilen uygulandığı ölçümle gösterildi** (sonsuz döngü ve bellek balonu gerçekten öldürülüyor) · denetim tablosundaki iki açık satır kapandı |

### Faz 3 — Sağlayıcı katmanı · *~2 saat*

| | |
|---|---|
| **Amaç** | Orkestratörü hangi LLM'in çalıştığından habersiz tutmak; anahtarsız çalışabilirliği sağlamak |
| **Üretilenler** | `llm/provider.py` (sözleşme) · `anthropic_provider.py` · `openai_provider.py` · `ollama_provider.py` · `replay_provider.py` (record + replay) · `tests/cassettes/` |
| **Tamamlanma** | Aynı çağrı dört sağlayıcıyla da yapılabiliyor · `.env` boşken sistem `replay` ile açılıyor · kaset kaydı sır taramasından geçiyor |

### Faz 4 — Agent'lar ve ana döngü · *~4 saat* · **ilk uçtan uca oyun**

| | |
|---|---|
| **Ön koşul** | `prompts/*.v1.md` **insan tarafından yazılmış** olmalı (K4) |
| **Üretilenler** | `agents/{base,planner,implementer,reviewer}.py` · `orchestrator/loop.py` · `tools/registry.py` · `tools/fs_mcp.py` |
| **Tamamlanma** | tic-tac-toe uçtan uca üretiliyor ve tarayıcıda oynanıyor · transkriptte **en az bir RED turu** görünüyor · denetleyici kararı yapısal JSON olarak ayrıştırılıyor · en az bir MCP çağrısı kayıtlı |

### Faz 5 — Arayüz · *~2 saat*

| | |
|---|---|
| **Üretilenler** | `web/app.py` SSE akışı · `static/index.html`: canlı transkript + oyun iframe'i + JSON/Markdown dışa aktarım |
| **Tamamlanma** | Transkript tur tur canlı akıyor · oyun yanında oynanıyor · `KK-07` (prompt hash'li dışa aktarım) geçiyor |

### Faz 6 — Kanıt ve teslim · *~4 saat*

| | |
|---|---|
| **Üretilenler** | `docs/analiz.md` · `docs/teknik.md` · `docs/kilavuz.md` · günlük konsolidasyonu · demo kaydı |
| **Tamamlanma** | Beş zorunlu teslim tam · **satranç hata senaryosu fiilen koşuldu ve çıktısı belgelendi** · 5 dk demo: snake (mutlu) + satranç veya limit aşımı (hata) |

---

## 3. Güne dağılım

| Gün | Fazlar | Gün sonu kanıtı |
|---|---|---|
| **1 · 14 Ağu** (yarım gün kaldı) | Faz 0, Faz 1 | Docker ayakta; durum makinesi testleri yeşil |
| **2 · 15 Ağu** | Faz 2, Faz 3, Faz 4 | İlk oyun üretildi, transkriptte red turu var |
| **3 · 16 Ağu** | Faz 5, Faz 6 | Beş teslim tam, demo çekildi |

**Paralel yürüyecek insan işi:** prompt yazımı (Gün 1 akşamı – Gün 2 sabahı, Faz 4'ten önce) ve eğitmenlere sorulacak üç açık soru (teslim formatı, demo canlı mı kayıt mı, bireysel mi ekip mi).

---

## 4. Kapsam daraltma sırası

Süre yetmezse **bu sırayla** kesilir — en az rubrik puanı kaybettiren önce:

| Sıra | Kesilecek | Kaybedilen | Neden önce bu |
|---|---|---|---|
| 1 | OpenAI + Ollama sağlayıcıları | Sağlayıcı çeşitliliği | Arayüz zaten yazılı; ikinci uygulama kanıt değil tekrar. Anthropic + replay yeter |
| 2 | Üretilebilir oyun sayısı 4 → 2 (tic-tac-toe, snake) | Kapsam genişliği | Mekanizma iki oyunda da aynı; üçüncü oyun yeni bir şey kanıtlamaz |
| 3 | SSE canlı akış → tur sonunda toplu yenileme | Arayüz cilası | Transkript içeriği aynı kalır; yalnızca akış estetiği gider |
| 4 | Markdown dışa aktarım (JSON kalır) | `KK-07`'nin yarısı | JSON denetlenebilirlik için yeterli |

**Asla kesilmeyecekler:** red/revizyon döngüsü (sistemin ana mekanizması), güvenlik testleri, zorunlu teslimler (eksiği diskalifiye eder).

---

## 5. Değişiklik kaydı

| Sürüm | Tarih | Değişiklik |
|---|---|---|
| 1.0 | 14.08.2026 | İlk sürüm — bağımlılık analizi, 7 faz, güne dağılım, kapsam daraltma sırası |
