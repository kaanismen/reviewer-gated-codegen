# PROJECT.md — Agent Oyun Atölyesi

> Bu dosya projenin **context paketidir**. Analist tarafından yazılır, geliştirici (ve geliştirici rolündeki AI aracı) bu dosyayla çalışır. Kod üretmeden önce bu dosya okunur; buradaki kurallar, şemalar ve limitler bağlayıcıdır.
>
> **Sürüm:** 1.0 · **Tarih:** 14 Ağustos 2026 · **Yazan:** Ümit İsmen (analist rolü)

---

## 1. Ürün tanımı

Kullanıcı bir sohbet kutusuna **"snake oyunu yaz"** yazar. Üç yapay zekâ agent'ı kendi aralarında konuşarak görevi tamamlar ve sonunda **tarayıcıda oynanabilir bir oyun** üretir.

```
Kullanıcı görevi
      │
      ▼
 PLANLAYICI ──► plan + kabul kriterleri
      │
      ▼
 UYGULAYICI ──► logic.js · logic.test.js · game.html
      │
      ▼
 DENETLEYİCİ ─► testleri çalıştırır, inceler
      │         yapısal JSON ile KABUL veya RED döner
      │
      └── RED ──► revizyon turu ──► UYGULAYICI
                                        │
                                   KABUL ▼
                          Teslim: çalışan oyun + transkript + denetim raporu
```

Sistemin ayırt edici özelliği agent'ların konuşması değil, **birbirini reddedebilmesidir.** Denetleyici, uygulayıcının çıktısını gerekçeli olarak geri çevirir ve revizyon ister. Bu döngü sistemin ana mekanizmasıdır, opsiyonel bir ekstra değil.

---

## 2. Kapsam

### 2.1 Kapsam içi

| Konu | Kapsam |
|---|---|
| Üretilebilir oyunlar | tic-tac-toe, snake, pong, breakout |
| Çıktı biçimi | Tek dosyalık `game.html` (canvas + JS) + ayrı `logic.js` mantık modülü |
| Test | `logic.js` üzerinde `node --test` ile çalışan `logic.test.js` |
| Agent sayısı | 3 (planlayıcı, uygulayıcı, denetleyici) |
| Arayüz | Web — canlı transkript + oyun iframe'i + transkript dışa aktarımı |
| Sağlayıcılar | Anthropic (Claude), OpenAI, Ollama, ve test için sahte sağlayıcı |
| Kalıcılık | Transkript ve üretilen dosyalar diske yazılır, oturum sonrası erişilebilir |

### 2.2 Kapsam dışı — gerekçeleriyle

| Konu | Neden dışarıda |
|---|---|
| **Satranç** | Rok, en passant, şah/mat tespiti ve geçerli hamle üretimi tek oturumda güvenilir üretim için fazla karmaşık. Sistemin bilinen sınırıdır ve 3. gün **hata senaryosu demosu** olarak bilinçli gösterilecektir. |
| Çok oyunculu / ağ üzerinden oyun | Ağ katmanı sandbox politikasıyla çelişir (sandbox'ta ağ kapalıdır) |
| 3B grafik, ses varlıkları, harici görsel | Tek dosyalık teslim kısıtını bozar; üretim süresi ve token maliyeti öngörülemez hale gelir |
| Kullanıcı hesabı, oturum yönetimi, çok kullanıcılı eşzamanlılık | 3 günlük süre kısıtı; tek kullanıcılı yerel çalıştırma varsayılmıştır |
| Agent'ların kendi promptlarını değiştirmesi | Promptlar sürümlü dosyalardır; çalışma anında değiştirilemez (denetlenebilirlik şartı) |
| Üretilen oyunun görsel kalitesinin otomatik değerlendirilmesi | Denetleyici mantığı test eder, estetiği değil |

### 2.3 Varsayımlar

| # | Varsayım | Doğrulanmazsa etkisi |
|---|---|---|
| V1 | Değerlendirici makinesinde **yalnızca Docker Desktop** (veya Docker Engine + Compose) kurulu | Tek ön koşuldur. Python, Node ve bağımlılıklar imajın içindedir; hostta hiçbir şey kurulmaz |
| V2 | En az bir LLM sağlayıcısına erişim var (veya Ollama lokal kurulu) | Sahte sağlayıcı ile kayıtlı senaryolar yine de çalışır |
| V3 | Tek kullanıcı, tek eşzamanlı görev | Eşzamanlı görev desteği yok; ikinci görev sıraya alınmaz, reddedilir |
| V4 | Üretilen oyun kodu güvenilmez kabul edilir | Tüm çalıştırma sandbox içinde; bkz. §6 |

### 2.4 Kısıtlar

| # | Kısıt |
|---|---|
| K1 | Toplam geliştirme süresi 3 gün (14–16 Ağustos 2026) |
| K2 | Teslimlerin tamamı zorunlu; eksik teslim projeyi değerlendirme dışı bırakır |
| K3 | Demo 5 dakika: mutlu senaryo + en az bir hata senaryosu |
| K4 | Prompt'lar insan tarafından yazılır; kod üretimi AI'a bırakılabilir (eğitim kuralı) |
| K5 | **Sistem eğitmenlerin kendi makinelerinde dockerize çalışabilmelidir.** Tek komutla ayağa kalkmalı, host'a Docker dışında kurulum gerektirmemelidir |

---

## 3. Mimari

### 3.1 Katmanlar

| Katman | Sorumluluk | Bilmediği şey |
|---|---|---|
| `orchestrator/` | Durum makinesi, tur döngüsü, tüm limitler | Hangi LLM'in kullanıldığı |
| `agents/` | Rol davranışı, prompt yükleme, çıktı ayrıştırma | Turların nasıl sıralandığı |
| `llm/` | Sağlayıcı arayüzü ve uygulamaları | Agent rollerini |
| `tools/` | İzin listeli araç kaydı, MCP istemcisi | Kimin çağırdığını |
| `sandbox/` | Docker konteyner yaşam döngüsü, izolasyon | Çalıştırdığı kodun ne olduğunu |
| `transcript/` | Olay kaydı, kalıcılık, dışa aktarım | İş mantığını |
| `security/` | Yol koruması, sır taraması, girdi sınırlama | — |
| `web/` | HTTP, SSE akışı, tek sayfa arayüz | Orkestrasyon iç detaylarını |

**Bağımlılık yönü tek yönlüdür:** `web → orchestrator → agents → {llm, tools} → sandbox`. Ters bağımlılık yasaktır. `security` ve `transcript` her katmandan çağrılabilir.

### 3.2 Dizin yapısı

```
gtech-agent-atolyesi/
├── PROJECT.md                    # bu dosya
├── README.md                     # kurulum + hızlı başlangıç
├── docker-compose.yml            # TEK ÇALIŞTIRMA YOLU: docker compose up
├── requirements.txt
├── .env.example                  # API anahtarı isimleri (değerler asla commit edilmez)
├── Dockerfile                    # tek imaj: python:3.11-slim + node 20 + runner kullanıcısı
├── prompts/                      # sürümlü sistem promptları
│   ├── planner.v1.md
│   ├── implementer.v1.md
│   └── reviewer.v1.md
├── src/
│   ├── orchestrator/  { state_machine.py, loop.py, limits.py }
│   ├── agents/        { base.py, planner.py, implementer.py, reviewer.py }
│   ├── llm/           { provider.py, anthropic_provider.py, openai_provider.py,
│   │                    ollama_provider.py, replay_provider.py }
│   ├── tools/         { registry.py, fs_mcp.py, test_runner.py }
│   ├── sandbox/       { process_runner.py, rlimits.py, import_guard.py }
│   ├── transcript/    { models.py, store.py }
│   ├── security/      { path_guard.py, secret_scan.py, input_guard.py }
│   └── web/           { app.py, static/index.html }
├── tests/
│   ├── test_state_machine.py
│   ├── test_limits.py
│   ├── test_security.py
│   ├── test_reviewer_parsing.py
│   └── cassettes/                # kaydedilmiş LLM yanıtları (record/replay)
├── workspaces/                   # üretilen oyunlar — .gitignore'da
└── docs/
    ├── ai-gunlugu.md
    ├── analiz.md
    ├── teknik.md
    └── kilavuz.md
```

### 3.3 Dağıtım mimarisi — dockerize çalıştırma

Sistem eğitmenin makinesinde **tek komutla** ayağa kalkar:

```
docker compose up
→ tarayıcıda http://localhost:8000
```

Host'ta Python, Node veya bağımlılık kurulumu **yoktur**. Tek ön koşul Docker'dır.

```
        Host makine (eğitmenin bilgisayarı)
        ── kurulu olması gereken tek şey: Docker ──
        ┌────────────────────────────────────────────────┐
        │  tarayıcı ──► localhost:8000                   │
        │                    │                           │
        │  ┌─────────────────▼────────────────────────┐  │
        │  │  TEK KONTEYNER  (python:3.11-slim + node)│  │
        │  │                                          │  │
        │  │  orkestratör · agents · web · MCP        │  │
        │  │            │                             │  │
        │  │            │ alt süreç (runner kullanıcı)│  │
        │  │            ▼                             │  │
        │  │  ┌────────────────────────────────────┐  │  │
        │  │  │ node --test                        │  │  │
        │  │  │ · ayrıcalıksız kullanıcı           │  │  │
        │  │  │ · rlimit: cpu/bellek/süreç/dosya   │  │  │
        │  │  │ · 30 sn timeout → SIGKILL          │  │  │
        │  │  │ · yol kısıtı: /workspaces/<id>     │  │  │
        │  │  │ · statik içe aktarma izin listesi  │  │  │
        │  │  └────────────────────────────────────┘  │  │
        │  └──────────────────┬───────────────────────┘  │
        │                     │ volume                   │
        │                     ▼                          │
        │              ./workspaces/                     │
        │        (üretilen oyunlar, hosttan görülebilir) │
        └────────────────────────────────────────────────┘
```

**Docker içinde Docker yoktur.** Uygulama konteyner başlatmaz, Docker soketi bağlanmaz. Bu bilinçli bir karardır: soket bağlama, uygulamaya host üzerinde root eşdeğeri yetki vererek onu izole ettiği koddan daha ayrıcalıklı hale getirirdi. Bunun yerine izolasyon **süreç düzeyinde**, konteyner sınırının içinde kurulur.

#### Sandbox — süreç düzeyinde katmanlı izolasyon

Üretilen kod, app sürecinin alt süreci olarak ama ayrı bir güvenlik bağlamında çalıştırılır:

| Katman | Uygulama | Engellediği |
|---|---|---|
| Ayrıcalık düşürme | `node`, root değil `runner` adlı ayrıcalıksız kullanıcı olarak çalışır | Konteyner içi dosya sistemine geniş erişim |
| `RLIMIT_CPU` | 25 sn CPU | Sonsuz döngü, CPU tüketimi |
| `RLIMIT_DATA` | 512 MB veri segmenti | Bellek tüketimi |
| `RLIMIT_NPROC` | 32 süreç | Fork bombası |
| `RLIMIT_FSIZE` | 10 MB | Disk doldurma |
| Duvar saati | 30 sn sonra `SIGKILL` | Askıda kalan süreç |
| Yol kısıtı | Çalışma dizini `/workspaces/<gorev_id>`; tüm yollar kanonikleştirilip kök altında doğrulanır | Workspace dışına okuma/yazma |
| **Statik içe aktarma izin listesi** | Kod **çalıştırılmadan önce** taranır: `node:net`, `node:http(s)`, `node:child_process`, `node:fs`, `node:worker_threads`, `fetch`, `eval`, `require('...')` dinamik biçimleri → reddedilir | Ağ erişimi, süreç başlatma, dosya sistemi kaçışı |
| Ortam temizliği | Alt sürece yalnızca izin listesindeki ortam değişkenleri geçirilir; API anahtarları asla geçmez | Anahtar sızıntısı |

**Bellek tavanı neden `RLIMIT_DATA`, `RLIMIT_AS` değil:** V8, pointer-compression için devasa bir **sanal** adres alanı ayırır; bu alan yerleşik bellek değildir ama `RLIMIT_AS` onu sayar. Ölçüm (`tests/manual/rlimit_olcumu.py`, 14.08.2026) `RLIMIT_AS=512 MB` altında **meşru** bir "hello world"ün bile `SIGTRAP` ile çöktüğünü, 128 MB altında ise asıldığını gösterdi. `RLIMIT_DATA` gerçek veri segmentini sınırlar: 512 MB'de meşru kod çalışır, 256 MB'de sınırsız ayırma `SIGABRT` ile durdurulur. Bu düzeltme spesifikasyona ölçümden sonra girmiştir.

**Statik izin listesi neden meşru:** üretilen oyun mantığı saf hesaplamadır — durum, kural, kazanma kontrolü. Ağ, süreç veya dosya sistemi erişimine ihtiyacı yoktur. Bu modüllerden birini kullanan bir çıktı ya hatalıdır ya kötücüldür; her iki durumda da çalıştırılmadan reddedilmesi doğru davranıştır. Red, denetleyiciye **kritik bulgu** olarak iletilir ve revizyon turu başlatır.

#### Yapılandırma

| Değişken | Varsayılan | Not |
|---|---|---|
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | *(boş)* | `.env` dosyasından okunur, imaja gömülmez |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama host'ta çalışır; Linux'ta `extra_hosts` ile eşlenir |
| `LLM_PROVIDER` | `anthropic` | `anthropic` \| `openai` \| `ollama` \| `replay` |
| `WEB_PORT` | `8000` | Host'a eşlenen port |

**Anahtarsız çalışabilirlik zorunludur.** `.env` boşsa sistem `replay` sağlayıcısıyla başlar ve kayıtlı senaryoları oynatır. Eğitmen hiçbir API anahtarı girmeden `docker compose up` yapıp sistemi uçtan uca çalışırken görebilir. Bu, "hatasız kurulabilen ürün" kriterinin en güçlü kanıtıdır.

#### İmaj kısıtları

| Kural | Gerekçe |
|---|---|
| **Tek imaj** — Python 3.11 + Node 20 aynı imajda | Docker içinde Docker yok; ikinci imaj gerekmiyor |
| `app` imajı < 500 MB, ilk derleme < 3 dk | Eğitmen değerlendirme sırasında bekletilmemeli |
| `pip install` ayrı katmanda, kod kopyalamadan önce | Katman önbelleği; kod değişince bağımlılıklar yeniden kurulmaz |
| İmajda `runner` adlı ayrıcalıksız kullanıcı tanımlı | Sandbox'ın ayrıcalık düşürme katmanı buna dayanıyor |
| `workspaces/` host'a bağlanır | Üretilen oyunlar konteyner kapansa da incelenebilir kalır |
| Host'ta kurulum: **yalnızca Docker** | Python, Node, npm, bağımlılıklar imajın içinde |

---

## 4. Durum makinesi

> Bu bölüm aynı zamanda **analist B bloğunun "durum makinesi tablosu"** teslimidir.

### 4.1 Durumlar

| Durum | Anlamı | Çıkış var mı |
|---|---|---|
| `PLANLANIYOR` | Planlayıcı görevi bölüyor | Evet |
| `UYGULANIYOR` | Uygulayıcı dosya yazıyor | Evet |
| `DENETLENIYOR` | Denetleyici test çalıştırıp inceliyor | Evet |
| `REDDEDILDI` | Denetleyici reddetti, revizyon kararı veriliyor | Evet (geçici durum) |
| `KABUL_EDILDI` | Teslim hazır | **Son durum** |
| `LIMIT_ASILDI` | Tur/token/süre/maliyet tavanı doldu veya ilerleme durdu | **Son durum** |
| `HATA` | Kurtarılamayan teknik hata | **Son durum** |

### 4.2 Geçiş tablosu

| # | Kaynak | Olay | Hedef | Koruma koşulu |
|---|---|---|---|---|
| G1 | *(başlangıç)* | görev alındı | `PLANLANIYOR` | Görev metni boş değil ve ≤ 2000 karakter |
| G2 | `PLANLANIYOR` | plan üretildi | `UYGULANIYOR` | Plan JSON şeması geçerli, ≥ 1 kabul kriteri var |
| G3r | `PLANLANIYOR` | şema hatası (1. kez) | `PLANLANIYOR` | Yeniden deneme hakkı var — planlayıcı tekrar çağrılır |
| G3 | `PLANLANIYOR` | şema hatası (2. kez) | `HATA` | Yeniden deneme hakkı tükendi |
| G4 | `UYGULANIYOR` | dosyalar yazıldı | `DENETLENIYOR` | ≥ 1 dosya yazıldı, tüm yollar workspace içinde |
| G5 | `UYGULANIYOR` | yol ihlali | `HATA` | Sandbox politikası ihlali — kurtarma yok |
| G6 | `DENETLENIYOR` | karar = `KABUL` | `KABUL_EDILDI` | Tüm testler geçti **ve** sır taraması temiz |
| G6s | `DENETLENIYOR` | karar = `KABUL` | `REDDEDILDI` | Sır taraması bulgu verdi — kabul geçersiz (KK-06) |
| G7 | `DENETLENIYOR` | karar = `RED` | `REDDEDILDI` | `tur < max_tur` |
| G8 | `DENETLENIYOR` | karar = `RED` | `LIMIT_ASILDI` | `tur >= max_tur` |
| G9r | `DENETLENIYOR` | karar ayrıştırılamadı (1. kez) | `DENETLENIYOR` | Yeniden deneme hakkı var (KK-05) |
| G9 | `DENETLENIYOR` | karar ayrıştırılamadı (2. kez) | `HATA` | Yapısal JSON dönmedi |
| G10 | `REDDEDILDI` | revizyon başlat | `UYGULANIYOR` | Red gerekçesi son 2 turdakiyle aynı değil |
| G11 | `REDDEDILDI` | ilerleme yok | `LIMIT_ASILDI` | Aynı red gerekçesi 2 kez üst üste |
| G12 | *(herhangi)* | token/süre/maliyet aşımı | `LIMIT_ASILDI` | Bkz. §5 |
| G13 | *(herhangi)* | beklenmeyen istisna | `HATA` | — |

**Olay seçimi `karar` alanına bakılarak yapılmaz.** `event_for_review()` tek giriş noktasıdır ve §7.4 iş kuralını uygular; böylece kuralı uygulamayı unutan bir çağrı yeri T4'ü yeniden açamaz.

**Her son durumda sistem gerekçeli bir rapor üretir.** `LIMIT_ASILDI` ve `HATA` sessizce sonlanmaz; hangi limitin dolduğu, hangi turda ve son red gerekçesinin ne olduğu transkripte ve kullanıcıya yazılır.

### 4.3 Kabul kriterleri (Given/When/Then)

> Analist A bloğu teslimi. Tam liste `docs/analiz.md` içindedir; aşağıdakiler durum makinesini doğrudan sınayanlardır.

- **KK-01** — *Given* geçerli bir görev girildi, *When* planlayıcı plan üretti, *Then* sistem `UYGULANIYOR` durumuna geçer ve planda en az bir kabul kriteri bulunur.
- **KK-02** — *Given* tur limiti 5, *When* denetleyici 5. turda hâlâ reddediyor, *Then* sistem durur, `LIMIT_ASILDI` durumuna geçer ve son red gerekçesini içeren başarısızlık raporu üretir.
- **KK-03** — *Given* denetleyici aynı gerekçeyle iki kez üst üste reddetti, *When* üçüncü tur başlatılacak, *Then* sistem ilerleme olmadığını tespit eder ve turu başlatmadan durur.
- **KK-04** — *Given* uygulayıcı workspace dışına yazmayı denedi, *When* yol koruması devreye girer, *Then* işlem reddedilir, `HATA` durumuna geçilir ve ihlal transkripte kaydedilir.
- **KK-05** — *Given* denetleyici serbest metin döndürdü, *When* JSON ayrıştırma başarısız olur, *Then* sistem kararı KABUL saymaz; bir kez yeniden dener, tekrar başarısız olursa `HATA` durumuna geçer.
- **KK-06** — *Given* tüm testler geçti, *When* denetleyici KABUL döndü, *Then* sır taraması çalıştırılır; anahtar/token bulunursa KABUL geçersiz sayılır ve red turu başlatılır.
- **KK-07** — *Given* sistem `KABUL_EDILDI` durumunda, *When* kullanıcı transkripti dışa aktarır, *Then* JSON ve Markdown çıktısı üretilir ve prompt sürüm hash'lerini içerir.

---

## 5. Kontrol limitleri

Tüm limitler `src/orchestrator/limits.py` içinde tek yerde tanımlıdır ve `.env` üzerinden geçersiz kılınabilir.

| Limit | Varsayılan | Amaç |
|---|---|---|
| `MAX_TUR` | 5 | Sonsuz döngü koruması |
| `MAX_TOKEN_TOPLAM` | 150.000 | Maliyet ve bağlam patlaması koruması |
| `MAX_MALIYET_USD` | 1.00 | Sert harcama tavanı |
| `MAX_SURE_SN` | 300 | Duvar saati koruması |
| `SANDBOX_TIMEOUT_SN` | 30 | Üretilen kodun sonsuz döngüsüne karşı |
| `ILERLEME_YOK_ESIGI` | 2 | Aynı red gerekçesi kaç kez tekrarlarsa durulur |
| `MAX_GOREV_KARAKTER` | 2000 | Girdi sınırlama (prompt injection yüzeyini daraltır) |
| `RLIMIT_CPU_SN` | 25 | Alt süreç CPU tavanı (bkz. §3.3) |
| `RLIMIT_BELLEK_MB` | 512 | Alt süreç veri segmenti tavanı (`RLIMIT_DATA`; gerekçe §3.3) |
| `RLIMIT_SUREC` | 32 | Fork bombası koruması |
| `RLIMIT_DOSYA_MB` | 10 | Disk doldurma koruması |

**Limit kontrolü her tur başında yapılır**, tur ortasında değil. Bir limit dolduğunda çalışan sandbox konteyneri sonlandırılır ve rapor üretilir.

---

## 6. Güvenlik politikası

Bu sistemin merkezinde **AI'ın ürettiği kodun gerçekten çalıştırılması** var. Dolayısıyla gerçek bir tehdit modeli mevcuttur ve aşağıdaki maddelerin her biri bir kabul testine karşılık gelir.

| # | Tehdit | Önlem | Test |
|---|---|---|---|
| T1 | Sandbox kaçışı — workspace dışına yazma | Tüm yollar kanonik hale getirilir (`Path.resolve()`) ve workspace kökü altında olduğu doğrulanır; `..`, mutlak yol ve sembolik bağlantı reddedilir | `test_security.py::test_yol_kacisi` |
| T2 | Keyfi kod yürütme | Yalnızca `node --test`; ayrıcalıksız `runner` kullanıcısı, `RLIMIT_CPU/DATA/NPROC/FSIZE`, 30 sn `SIGKILL`, workspace'e kısıtlı çalışma dizini, temizlenmiş ortam değişkenleri (bkz. §3.3) | `test_security.py::test_kaynak_limitleri`, `::test_zaman_asimi` |
| T2b | **Ağ üzerinden sızma / dışa veri aktarımı** | Kod **çalıştırılmadan önce** statik olarak taranır; `node:net`, `node:http(s)`, `node:child_process`, `node:fs`, `node:worker_threads`, `fetch`, `eval` ve dinamik `require` biçimleri reddedilir. Red, denetleyiciye kritik bulgu olarak iletilir | `test_security.py::test_ice_aktarma_izin_listesi` |
| T3 | Prompt injection | Görev metni **veri** olarak sınırlandırılmış blok içinde iletilir; agent promptları çalışma anında değiştirilemez; görev metni karakter sınırına tabidir | `test_security.py::test_gorev_metni_talimat_olarak_islenmez` |
| T4 | **Sahte KABUL** | Denetleyicinin kararı **yapısal JSON** olarak ayrıştırılır. Serbest metin içinde geçen "KABUL" kelimesi karar sayılmaz — üretilen kodun içindeki bir yorum satırı sistemi kandıramaz | `test_reviewer_parsing.py` |
| T5 | Sır sızıntısı | Üretilen kod ve transkript, yaygın anahtar desenlerine karşı taranır; bulgu varsa KABUL geçersizdir ve transkriptte maskelenir | `test_security.py::test_sir_taramasi` |
| T6 | Maliyet/DoS | §5'teki tüm limitler; ayrıca ilerleme-yok tespiti | `test_limits.py` |
| T7 | API anahtarı sızıntısı | Anahtarlar yalnızca ortam değişkeninden okunur, asla transkripte veya loga yazılmaz, `.env` `.gitignore`'dadır | Kod incelemesi + `test_security.py::test_anahtar_loglanmaz` |

### Bilinen sınırlar — dürüstçe belgelenmiştir

Aşağıdakiler kapatılmamış açıklardır. Gizlenmeleri yerine, sonuçlarıyla birlikte yazılmaları tercih edilmiştir; `docs/teknik.md` içinde de yer alacaklardır.

| # | Sınır | Sonuç | Neden kabul edildi / azaltıcı faktör |
|---|---|---|---|
| S1 | **Test alt süreci için ağ ad alanı izolasyonu yoktur** | Konteynerin ağ erişimi vardır (LLM API'sine gitmesi gerekir) ve alt süreç bunu miras alır. Ayrı ağ ad alanı, ayrı konteyner gerektirirdi | Docker içinde Docker bilinçli olarak reddedildi (§3.3). Telafi: **statik içe aktarma izin listesi** — ağ modülü kullanan kod çalıştırılmadan reddedilir (T2b). Ayrıca üretilen oyun mantığı saf hesaplamadır; ağa meşru ihtiyacı yoktur |
| S2 | Statik içe aktarma denetimi desen tabanlıdır | Yeterince gizlenmiş kod (dize birleştirmeyle modül adı üretme gibi) teoride denetimi atlatabilir | Dinamik `require`/`import()` biçimleri de topluca reddedilerek gizleme yüzeyi daraltıldı. Atlatılsa dahi kod hâlâ ayrıcalıksız kullanıcı, rlimit ve konteyner sınırı içindedir — tek katman değil, **son katman** delinmiş olur |
| S3 | Sır taraması desen tabanlıdır | Bilinmeyen formatta bir anahtar yakalanmayabilir | 3 günlük kapsamda entropi tabanlı tarama kapsam dışı bırakıldı. API anahtarları alt sürece hiçbir zaman geçirilmez (ortam temizliği), dolayısıyla üretilen kodun sızdıracak bir anahtarı yoktur |
| S4 | Konteyner kaçışı bu projenin tehdit modeli dışındadır | Docker'ın kendi izolasyonundaki bir zafiyet varsayılmamıştır | Konteyner sınırı en dış katmandır; onun ötesi platform sorumluluğudur |

**Katman sayısı bilinçlidir.** Yukarıdaki sınırların hiçbiri tek başına savunmayı çökertmez: bir saldırının hedefe ulaşması için statik denetimi, ayrıcalık düşürmeyi, kaynak limitlerini, yol kısıtını ve konteyner sınırını **arka arkaya** aşması gerekir. Tasarım hedefi kusursuz izolasyon değil, **her katmanın bağımsız ve test edilebilir olmasıdır.**

---

## 7. Mesaj şeması ve alan sözlüğü

> Bu bölüm **analist B bloğunun "alan sözlüğü"** teslimidir: her alanın tipi, zorunluluğu ve iş kuralı yazılıdır.

### 7.1 Ortak zarf — `AgentMesaji`

| Alan | Tip | Zorunlu | İş kuralı |
|---|---|---|---|
| `id` | UUID4 | ✔ | Sistem üretir, benzersiz |
| `tur` | int | ✔ | 1'den başlar, her uygulayıcı→denetleyici çevriminde artar |
| `rol` | enum: `planlayici` \| `uygulayici` \| `denetleyici` \| `sistem` | ✔ | Rol dışı değer reddedilir |
| `zaman` | ISO-8601 UTC | ✔ | Sistem üretir |
| `icerik` | object | ✔ | Şeması `rol` alanına göre belirlenir (aşağıda) |
| `prompt_surumu` | string | ✔ | Örn. `planner.v1` — denetlenebilirlik için zorunlu |
| `prompt_hash` | sha256 (ilk 12 hane) | ✔ | Prompt dosyasının içerik hash'i; sonradan değiştirilmediğini kanıtlar |
| `model` | string | ✔ | Kullanılan model kimliği, örn. `claude-opus-5` |
| `token_girdi` | int | ✔ | ≥ 0 |
| `token_cikti` | int | ✔ | ≥ 0 |
| `maliyet_usd` | decimal(8,5) | ✔ | Sağlayıcı fiyatından hesaplanır; Ollama için `0` |

**Köken alanlarının zorunluluğu rol bazlıdır.** `prompt_surumu`, `prompt_hash` ve `model` **agent rolleri için zorunludur** — bu üçü olmadan bir agent mesajı transkripte giremez. `rol = sistem` mesajlarının promptu ve modeli olmadığından bu alanlar onlarda boştur. v1.0'da kural koşulsuz yazılmıştı; Faz 1'de sistem mesajları eklenince rol bazlı hale getirildi.

### 7.2 `icerik` — planlayıcı

| Alan | Tip | Zorunlu | İş kuralı |
|---|---|---|---|
| `oyun` | enum: `tic-tac-toe` \| `snake` \| `pong` \| `breakout` | ✔ | Kapsam dışı oyun istenirse plan üretilmez, gerekçeli ret döner |
| `adimlar` | string[] | ✔ | 2–6 adım; boş liste geçersiz |
| `kabul_kriterleri` | string[] | ✔ | **En az 1 zorunlu.** Her biri test edilebilir bir ifade olmalı |
| `dosyalar` | string[] | ✔ | Üretilecek dosya adları; workspace'e göreli |

### 7.3 `icerik` — uygulayıcı

| Alan | Tip | Zorunlu | İş kuralı |
|---|---|---|---|
| `yazilan_dosyalar` | object[] | ✔ | Her biri `{yol, bayt, hash}`; en az 1 kayıt |
| `arac_cagrilari` | object[] | ✔ | MCP çağrı kaydı; her biri `{arac, ozet, basarili}`. Boş olabilir ama alan zorunlu |
| `not` | string | ✖ | Uygulayıcının serbest açıklaması; karar üzerinde etkisi yok |

### 7.4 `icerik` — denetleyici *(kritik şema)*

| Alan | Tip | Zorunlu | İş kuralı |
|---|---|---|---|
| `karar` | enum: `KABUL` \| `RED` | ✔ | **Sadece bu iki değer.** Ayrıştırılamayan karar KABUL sayılmaz (bkz. T4) |
| `gerekce` | string | ✔ | 10–500 karakter. `RED` için boş olamaz |
| `bulgular` | object[] | ✔ | Her biri `{dosya, sorun, onem}`; `onem` ∈ `kritik` \| `orta` \| `dusuk`. `KABUL` için boş liste olabilir |
| `test_sonucu` | object | ✔ | `{gecen: int, kalan: int, cikti: string}` |

**İş kuralı — karar tutarlılığı:** `karar = KABUL` iken `test_sonucu.kalan > 0` ise sistem kararı geçersiz sayar ve `RED` olarak işler. Denetleyici kendi test sonucuyla çelişemez.

### 7.5 Transkript kaydı

Transkript, `AgentMesaji` listesine ek olarak şu üstveriyi taşır: görev metni, başlangıç/bitiş zamanı, son durum, tüketilen token/maliyet toplamı, kullanılan sağlayıcı ve model eşlemesi, tüm prompt sürüm hash'leri. JSON ve Markdown olarak dışa aktarılabilir.

---

## 8. Sağlayıcı politikası

### 8.1 Rol–model eşlemesi

| Rol | Varsayılan model | Gerekçe |
|---|---|---|
| Planlayıcı | `claude-opus-5` | Plan ve kabul kriteri kalitesi işin geri kalanını belirler |
| Uygulayıcı | `claude-sonnet-5` | Token'ın çoğunu bu rol harcar; tanıtım fiyatıyla en iyi maliyet/kalite dengesi |
| Denetleyici | `claude-opus-5` | Red kararının isabetli olması sistemin ana döngüsüdür |
| Tümü (offline) | Ollama — yerel model | Ağ/kota bağımsız demo yedeği, sıfır maliyet |
| Tümü (test) | `replay_provider` | Kayıtlı yanıtlar; deterministik, API'siz, saniyeler içinde |

Eşleme `.env` üzerinden rol bazında değiştirilebilir. OpenAI sağlayıcısı arayüzü uygular ve seçenek olarak sunulur.

### 8.2 Sağlayıcı arayüzü sözleşmesi

Her sağlayıcı tek bir yöntemi uygular: bir sistem promptu, mesaj listesi ve araç tanımları alır; metin/araç çağrısı, token sayıları ve maliyeti döndürür. **Orkestratör hangi sağlayıcının çalıştığını bilmez.** Sağlayıcı değişimi tek satır yapılandırma değişikliğidir.

### 8.3 Record/replay

`replay_provider`, gerçek çağrıların istek-yanıt çiftlerini `tests/cassettes/` altına kaydeder ve test modunda tekrar oynatır. Kabul testleri **API anahtarı olmadan** çalışır. Kayıt dosyaları sır taramasından geçirilerek commit edilir.

---

## 9. Prompt yönetimi

| Kural | Detay |
|---|---|
| Ayrı dosya | Her rolün sistem promptu `prompts/<rol>.v<n>.md` içindedir; koda gömülmez |
| Sürümleme | Prompt değişince yeni sürüm dosyası açılır; eskisi silinmez |
| Hash kaydı | Yüklenen promptun sha256'sı her mesajda taşınır |
| Görev metni ayrımı | Kullanıcı görevi promptun içine gömülmez; ayrı, sınırlandırılmış bir **veri bloğu** olarak iletilir |
| Çalışma anında değişmez | Agent'lar kendi veya birbirinin promptunu değiştiremez |

---

## 10. Test stratejisi

| Katman | Yaklaşım |
|---|---|
| Durum makinesi | Saf birim testleri — LLM yok, sandbox yok |
| Limitler | Sahte saat ve sayaçlarla sınır durumları |
| Güvenlik | §6'daki her tehdit için en az bir negatif test |
| Denetleyici ayrıştırma | Bozuk JSON, serbest metin, çelişkili karar senaryoları |
| Uçtan uca | `replay_provider` ile kayıtlı senaryolar — deterministik |

**Kural:** Hiçbir otomatik test gerçek API çağrısı yapmaz. Gerçek sağlayıcılar yalnızca elle çalıştırılan senaryolarla ve demo sırasında devrededir.

---

## 11. Kodlama kuralları

- Python 3.11+, tip ipuçları zorunlu, `dataclass` veya `pydantic` ile şema doğrulama.
- Türkçe alan adları **yalnızca** mesaj şemasında (§7) kullanılır — bunlar iş alanı terimleridir. Python tanımlayıcıları İngilizce.
- Sabitler tek yerde: limitler `limits.py`, yollar `config.py`. Sihirli sayı yasak.
- Her modül tek sorumluluk. Katman ihlali (§3.1) yasak.
- Yorum satırı yalnızca kodun kendi gösteremediği bir kısıtı açıklamak için yazılır.
- Sır asla koda gömülmez; yalnızca ortam değişkeni.

---

## 12. Tamamlanma tanımı

Bir teslim, aşağıdakilerin tamamı sağlandığında bitmiş sayılır:

| Teslim | Tamamlanma ölçütü |
|---|---|
| Çalışan ürün | **Docker'dan başka hiçbir şey kurulu olmayan temiz bir makinede**, depo klonlanıp `docker compose up` ile ayağa kalkıyor; `.env` boşken bile `replay` moduyla uçtan uca çalışıyor; anahtar girildiğinde en az 2 farklı oyunu gerçekten üretebiliyor |
| Analiz dokümanı | User story'ler, Given/When/Then kabul kriterleri, kapsam/kapsam dışı, varsayım ve kısıt tablosu tam |
| Teknik doküman | Mimari şeması, veri modeli, API sözleşmesi, model/sağlayıcı karar tablosu, bilinen sınırlar |
| Kullanım kılavuzu | Ekran görüntülü kurulum ve kullanım; en az bir hata durumunun ne anlama geldiği açıklanmış |
| AI çalışma günlüğü | Her oturum kayıtlı; karar sahipliği ve denetim notları güncel |
| Demo | 5 dk: snake üretimi (mutlu senaryo) + satranç denemesi veya limit aşımı (hata senaryosu) |
| Testler | §6'daki 7 tehdidin her biri için geçen bir test mevcut |

---

## 13. Değişiklik kaydı

| Sürüm | Tarih | Değişiklik |
|---|---|---|
| 1.0 | 14.08.2026 | İlk sürüm — kapsam, mimari, durum makinesi, şemalar, güvenlik politikası |
| 1.1 | 14.08.2026 | **Eğitmen makinesinde dockerize çalışma şartı eklendi (K5).** §3.3 dağıtım mimarisi, iki kademeli sandbox modu, anahtarsız `replay` başlangıcı ve imaj kısıtları eklendi. §6'ya Docker soketi bağlama takası (S1) ve yedek mod izolasyon zaafı (S2) bilinen sınır olarak yazıldı. §2.3 V1 ve §12 tamamlanma ölçütü güncellendi |
| 1.4 | 14.08.2026 | **Faz 1 — uygulamadan geri beslenen spesifikasyon boşlukları.** §4.2'ye üç geçiş eklendi: G3r ve G9r (tabloda "2. kez" denen yeniden deneme haklarının 1. kez dalları yazılı değildi), G6s (KK-06'daki "sır bulunursa KABUL geçersiz" dalı tabloda yoktu). §4.2'ye `event_for_review()` kuralı, §7.1'e köken alanlarının rol bazlı zorunluluğu, §7.3'e `arac_cagrilari` iç şeması eklendi. 95 test yeşil |
| 1.3 | 14.08.2026 | **Ölçüm düzeltmesi (Faz 0).** Docker Desktop/WSL2 altında yapılan ölçüm, `RLIMIT_AS`'in Node için yanlış kaldıraç olduğunu gösterdi — 512 MB'de meşru kod bile çöküyor. Bellek tavanı `RLIMIT_DATA`ya çevrildi; §3.3'e gerekçe ve ölçüm referansı, §5'e not eklendi, §6/T2 güncellendi. Ölçüm betiği: `tests/manual/rlimit_olcumu.py`. Diğer üç rlimit, ayrıcalık düşürme ve duvar saati doğrulandı |
| 1.2 | 14.08.2026 | **Docker içinde Docker kaldırıldı.** Tek konteyner, tek imaj (Python + Node); Docker soketi bağlanmıyor, uygulama konteyner başlatmıyor. Sandbox artık süreç düzeyinde katmanlı izolasyon: ayrıcalık düşürme, rlimit'ler, zaman aşımı, yol kısıtı, ortam temizliği ve yeni **statik içe aktarma izin listesi** (T2b). §6 bilinen sınırlar tablosu baştan yazıldı — eski S1 (soket ayrıcalığı) ve S2 (yedek mod) ortadan kalktı; yerine ağ ad alanı izolasyonunun yokluğu (S1) ve desen tabanlı denetimin sınırı (S2) geldi. §5'e rlimit değerleri eklendi |
