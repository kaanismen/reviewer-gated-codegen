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
| Üretilebilir oyunlar | **İsim listesiyle değil ölçütle belirlenir** (bkz. §2.1.1). Bilinen-iyi örnekler: tic-tac-toe, snake, pong, breakout |
| Çıktı biçimi | Tek dosyalık `game.html` (canvas + JS) + ayrı `logic.js` mantık modülü |
| Test | `logic.js` üzerinde `node --test` ile çalışan `logic.test.js` |
| Agent sayısı | 3 (planlayıcı, uygulayıcı, denetleyici) |
| Arayüz | Web — canlı transkript + oyun iframe'i + transkript dışa aktarımı |
| Sağlayıcılar | Anthropic (Claude), OpenAI, Ollama, ve test için sahte sağlayıcı |
| Kalıcılık | Transkript ve üretilen dosyalar diske yazılır, oturum sonrası erişilebilir |
| **Oyun kütüphanesi** | Her görev kendi dizininde kalır; üretilen oyunlar listelenir ve arayüzden **aralarında geçiş yapılır**. Yeni bir görev öncekini ezmez |

### 2.1.1 Uygulanabilirlik ölçütü

Sabit bir oyun listesi, "başa çıkabileceğimiz karmaşıklık" için **kötü bir vekil ölçüdür**: connect-4 listede olmadığı için reddedilirdi, oysa snake'ten kolaydır. Ölçütün kendisi yazılır, sonucu değil:

| # | Ölçüt | Geçemezse |
|---|---|---|
| U1 | Oyun durumu tek bir veri yapısında tutulabiliyor mu | Kapsam dışı |
| U2 | Özel durum (kural istisnası) sayısı ≤ 10 mu | Kapsam dışı |
| U3 | Bitiş/kazanma koşulu **saf fonksiyonla** test edilebiliyor mu | Kapsam dışı |
| U4 | Harici varlık **dosyası** (`.png`, `.mp3`, sprite atlası, veri kümesi) gerekiyor mu | Gerekiyorsa kapsam dışı (§2.2) |
| U5 | Gerçek zamanlı animasyon gerekiyor mu | **Tek başına diskalifiye etmez** — pong ve breakout kapsam içidir |

**U4 kodla üretilen varlığı kapsamaz.** Ölçüt "ses veya grafik olmasın" değil, "ayrı dosya taşınmasın" der — kısıtın kaynağı tek dosyalık teslimdir (§2.2), sesin kendisi değil. Canvas çizimleri ve Web Audio osilatörüyle üretilen tonlar saf koddur ve `harici_varlik_gerekli = false` sayılır. Sınama sorusu: *"Bu oyun tek bir HTML dosyası olarak, yanında başka hiçbir dosya olmadan teslim edilebilir mi?"* Bu ayrım olmadan **flappy bird gibi kapsam içi olması gereken oyunlar yalnızca tıklama sesi yüzünden reddedilirdi.**

Planlayıcı bu değerlendirmeyi **yapısal veri olarak** döndürür (§7.2), serbest metin olarak değil; böylece denetlenebilir ve sınanabilir. Ölçütü geçemeyen görev `KAPSAM_DISI` son durumuna gider — bu bir hata değil, gerekçeli bir rettir.

### 2.2 Kapsam dışı — gerekçeleriyle

| Konu | Neden dışarıda |
|---|---|
| **Satranç** | Adı yasaklı olduğu için değil, **U2 ölçütünü geçemediği için**: rok, en passant, şah/mat, piyon terfisi, pat ve geçerli hamle üretimi özel durum tavanını fazlasıyla aşar. Sistem bunu çalışma anında değerlendirir ve gerekçeli olarak reddeder. 3. gün **hata senaryosu demosu** budur. |
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
│   ├── llm/           { provider.py, pricing.py, factory.py, anthropic_provider.py,
│   │                    openai_provider.py, ollama_provider.py, replay_provider.py }
│   ├── tools/         { registry.py, fs_mcp.py, test_runner.py }
│   ├── sandbox/       { process_runner.py, rlimits.py, import_guard.py }
│   ├── transcript/    { models.py, store.py, library.py }
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

**Fırlatıcı süreç, `preexec_fn` değil.** Limitler ve ayrıcalık düşürme, `subprocess`'in `preexec_fn` kancasıyla değil, ayrı bir **fırlatıcı süreci** (`sandbox/launcher.py`) tarafından uygulanır. Gerekçe: `preexec_fn`, `fork` ile `exec` arasında çalışır ve çok iş parçacıklı bir süreçte (uvicorn) kilitlenme riski taşır — Python belgeleri bunu açıkça uyarır. Fırlatıcı normal bir alt süreçtir, limitleri kendi üzerine uygular ve `exec` ile hedefe devreder; kaynak limitleri `exec` sınırını aşarak korunur. Fırlatıcı **projeden hiçbir şey içe aktarmaz**, böylece alt sürecin ortamı (`PYTHONPATH` dahil) tamamen temizlenebilir.

**Erişim devri.** Ayrıcalık düşürmenin doğrudan sonucu: workspace dizinini root açar, kodu `runner` çalıştırır. Devir yapılmazsa `node` dizini `stat` bile edemez ve hata "üretilen kod bozuk" gibi görünür. `ProcessRunner.grant_access()` bunu çalıştırmadan hemen önce yapar — ve **yalnızca statik denetimi geçmiş kod için**: reddedilen kodun dizini hiç devredilmez.

**Statik izin listesi neden meşru:** üretilen oyun mantığı saf hesaplamadır — durum, kural, kazanma kontrolü. Ağ, süreç veya dosya sistemi erişimine ihtiyacı yoktur. Bu modüllerden birini kullanan bir çıktı ya hatalıdır ya kötücüldür; her iki durumda da çalıştırılmadan reddedilmesi doğru davranıştır. Red, denetleyiciye **kritik bulgu** olarak iletilir ve revizyon turu başlatır.

#### Yapılandırma

| Değişken | Varsayılan | Not |
|---|---|---|
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | *(boş)* | `.env` dosyasından okunur, imaja gömülmez |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama host'ta çalışır; Linux'ta `extra_hosts` ile eşlenir |
| `LLM_PROVIDER` | `anthropic` | `anthropic` \| `openai` \| `ollama` \| `replay` |
| `WEB_PORT` | `8000` | Host'a eşlenen port |

#### Rol bazlı anahtar girişi

Son kullanıcı, her agent için **kendi API anahtarını arayüzden** girebilir; planlayıcı Anthropic, uygulayıcı OpenAI gibi karışık kurulumlar mümkündür. Bu, sisteme üçüncü taraf kimlik bilgisi emanet etmek demektir, dolayısıyla kasanın sözleşmesi dar tutulmuştur:

| Kural | Uygulama | Kapattığı sızıntı yolu |
|---|---|---|
| **Diske yazılmaz** | Yalnızca süreç belleğinde (`KeyVault`); konteyner yeniden başlayınca kaybolur | Transkript, workspace, log dosyası, yedek |
| **Geri okunamaz** | Arayüze yalnızca `{maske: "••••9f3a", uzunluk, saglayici, kaynak}` döner. `get()` yalnızca sağlayıcı istemcisini kuran kod tarafından çağrılır | API yanıtından geri okuma |
| **Log'a giremez** | `SecretStr` + kasaya özel `__repr__`/`__str__` | İstisna izleri (traceback), hata ayıklama çıktısı |
| **Metinden silinir** | `redact()` bilinen anahtarları **birebir dize** eşleşmesiyle siler; ortamdaki anahtarlar da bilinen sayılır | Sağlayıcı hata mesajının (401 vb.) transkripte yazılması |
| **Hata mesajı yankılamaz** | `KeyRejected` yalnızca uzunluk/biçim söyler, değeri asla | Doğrulama hatasının HTTP yanıtına düşmesi |
| **Alt sürece geçmez** | Ortam temizliği (§3.3 sandbox tablosu); kasa `os.environ`'a hiç yazmaz | Üretilen kodun anahtarı okuması |
| **Ağa açılmaz** | Konteyner portu `127.0.0.1`'e bağlanır, `0.0.0.0`'a değil | Yerel ağdaki başka bir makinenin anahtarı kullanması |

`redact()`'in **desen değil birebir eşleşme** kullanması önemlidir: anahtarın tam değeri bilindiği için, sır taramasının desen tabanlı olmasından kaynaklanan belirsizlik (bilinen sınır S3) kullanıcı anahtarları için geçerli değildir.

Arayüzden girilen anahtar, ortam değişkenini geçersiz kılar — daha yeni ve daha açık bir niyettir.

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
| `KAPSAM_DISI` | Görev uygulanabilirlik ölçütünü geçemedi, gerekçeli ret verildi | **Son durum** |
| `LIMIT_ASILDI` | Tur/token/süre/maliyet tavanı doldu veya ilerleme durdu | **Son durum** |
| `HATA` | Kurtarılamayan teknik hata | **Son durum** |

### 4.2 Geçiş tablosu

| # | Kaynak | Olay | Hedef | Koruma koşulu |
|---|---|---|---|---|
| G1 | *(başlangıç)* | görev alındı | `PLANLANIYOR` | Görev metni boş değil ve ≤ 2000 karakter |
| G2 | `PLANLANIYOR` | plan üretildi | `UYGULANIYOR` | Uygulanabilirlik = `UYGUN` **ve** ≥ 1 kabul kriteri var |
| G2k | `PLANLANIYOR` | plan üretildi | `KAPSAM_DISI` | Uygulanabilirlik = `UYGUN_DEGIL` — gerekçeli ret (§2.1.1) |
| G3r | `PLANLANIYOR` | şema hatası (1. kez) | `PLANLANIYOR` | Yeniden deneme hakkı var — planlayıcı tekrar çağrılır |
| G3 | `PLANLANIYOR` | şema hatası (2. kez) | `HATA` | Yeniden deneme hakkı tükendi |
| G4 | `UYGULANIYOR` | dosyalar yazıldı | `DENETLENIYOR` | ≥ 1 dosya yazıldı, tüm yollar workspace içinde |
| G4r | `UYGULANIYOR` | şema/kesilme hatası (1. kez) | `UYGULANIYOR` | Yeniden deneme hakkı var; kesilmeyse çıktı bütçesi büyütülür |
| G4e | `UYGULANIYOR` | şema/kesilme hatası (2. kez) | `HATA` | Yeniden deneme hakkı tükendi |
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

**Kesilme, şema hatasından ayrı tanınır.** Sağlayıcının `durdurma_nedeni` alanı `max_tokens` (Anthropic) veya `length` (OpenAI) ise yanıt token tavanına takılıp yarıda kesilmiştir. Bu, JSON ayrıştırmasından **önce** kontrol edilir; aksi hâlde yarım kalmış bir yanıt "JSON kapanmamış" diye raporlanır ve hata bütçe sorunu değil, modelin şemayı anlamaması gibi görünür. Kesilme sonrası yeniden denemede çıktı bütçesi 1.5 kat büyütülür (tavan 64.000) ve modele **daha kısa yazması** söylenir — aynı bütçeyle tekrar denemek aynı yerde kesilir.

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

**Limit kontrolü her tur başında yapılır**, tur ortasında değil. Bir limit dolduğunda çalışan sandbox süreci sonlandırılır ve rapor üretilir.

### 5.1 Ölçülen değerler (15.08.2026, gerçek koşular)

Tavanların yerinde olup olmadığı ancak gerçek tüketim bilinince anlaşılır:

| Görev | Sonuç | Tur | Girdi tok. | Çıktı tok. | Maliyet | Süre |
|---|---|---|---|---|---|---|
| tic-tac-toe | `KABUL_EDILDI` | 1 | 7.377 | 6.304 | **$0.221** | ~85 sn |
| connect-4 | `KABUL_EDILDI` | 1 | ~7.000 | ~6.000 | **$0.179** | ~90 sn |
| satranç | `KAPSAM_DISI` | 1 | 74 | 1.040 | **$0.012** | ~15 sn |
| snake *(yalnızca OpenAI, `gpt-5.4`)* | `KABUL_EDILDI` | 1 | 13.141 | 5.126 | ≤ $0.388 ¹ | ~40 sn |

¹ **Üst sınır.** `gpt-5.4` fiyatı `pricing.py` tablosunda yok; maliyet en pahalı bilinen tarifeden hesaplandı. Transkripte bu durumu bildiren bir sistem mesajı yazılır (`maliyet_ust_sinir`) — rakam kesin bir değermiş gibi sunulmaz. **Kullanıcı raporuna göre gerçek maliyet ≈ $0,10**, yani üst sınır yaklaşık **4 kat** yüksek. Tahmin bilinçli olarak yukarı yuvarlanıyor (§8.5); tabloya tahminî bir fiyat **eklenmedi**, çünkü harcama tavanını besleyen bir tabloya doğrulanmamış sayı girmek bu projenin baştan beri kaçındığı hata olurdu.

**Sağlayıcı değişimi tek satır yapılandırma çıktı.** `LLM_PROVIDER=openai` + `MODEL_*=gpt-5.4` ile üç rol de OpenAI'a geçti; kodda hiçbir değişiklik gerekmedi. §8.2'deki "orkestratör hangi sağlayıcının çalıştığını bilmez" iddiası böylece ölçülmüş oldu.

**Prompt önbelleğinin farkı burada görünüyor.** Anthropic koşusunda girdi 7.377 token'dı, OpenAI'da 13.141 — aradaki fark büyük ölçüde önbelleğe alınan sistem promptu. OpenAI sağlayıcısında önbellek kullanılmıyor.

**Tavanlar fazlasıyla geniş.** `MAX_TOKEN_TOPLAM` 150.000, gerçek tüketim ~13.700 — yani tek turlu bir koşu tavanın %9'unu kullanıyor. Beş turluk en kötü durum bile tavanın altında kalır. Tavanlar düşürülmedi: amaçları normal kullanımı sınırlamak değil, **kontrolden çıkmış bir döngüyü durdurmak**.

**Prompt önbelleği beklenenden etkili.** Planlayıcının ücretli girdi token'ı 74'e indi; ~2.500 token'lık sistem promptu önbelleğe yazıldı. Sonraki koşularda okuma katsayısı 0.1x olduğundan bu kalem neredeyse sıfırlanır.

---

## 6. Güvenlik politikası

Bu sistemin merkezinde **AI'ın ürettiği kodun gerçekten çalıştırılması** var. Dolayısıyla gerçek bir tehdit modeli mevcuttur ve aşağıdaki maddelerin her biri bir kabul testine karşılık gelir.

| # | Tehdit | Önlem | Test |
|---|---|---|---|
| T1 | Sandbox kaçışı — workspace dışına yazma | Tüm yollar kanonik hale getirilir (`Path.resolve()`) ve workspace kökü altında olduğu doğrulanır; `..`, mutlak yol, null bayt, ters bölü ve **dışarıyı gösteren sembolik bağlantı** reddedilir | `test_security.py` (T1 bölümü, 8 test) |
| T2 | Keyfi kod yürütme | Yalnızca `node --test`; ayrıcalıksız `runner` kullanıcısı, `RLIMIT_CPU/DATA/NPROC/FSIZE/CORE`, süreç grubuna `SIGKILL`, workspace'e kısıtlı çalışma dizini, temizlenmiş ortam (yalnızca `PATH`, `HOME`, `LANG`, `NODE_ENV`), 64 KB çıktı tavanı | `test_sandbox.py` (10 test — gerçek süreç başlatır) |
| T2b | **Ağ üzerinden sızma / dışa veri aktarımı** | Kod **çalıştırılmadan önce** statik olarak taranır. Yaklaşım **izin listesidir**: yalnızca `node:test`, `node:assert`, `node:assert/strict` ve göreli yollar geçer; bilinmeyen her modül reddedilir. Ayrıca dinamik `require`/`import`, `eval`, `new Function`, `fetch`, `XMLHttpRequest`, `process.env`, `process.binding`, `process.dlopen`, `WebAssembly` reddedilir. Red, denetleyiciye **kritik bulgu** olarak iletilir ve kod hiç çalıştırılmaz | `test_security.py` (T2b bölümü, 26 test) |
| T2c | **Tarayıcıda çalışan üretilmiş kod** | Oyun tarayıcıda çalışır, yani §3.3'teki süreç sandbox'ının **dışındadır**; oradaki katmanların hiçbiri geçerli değildir. Kendi kısıtı sunum katmanında kurulur: `connect-src 'none'` ağ çıkışını (fetch/XHR/WebSocket) kapatır, `img-src data:` uzak görsel URL'si üzerinden sızıntıyı engeller, `form-action 'none'` form gönderimini keser. Oyun `sandbox="allow-scripts"` ile gömülür — **`allow-same-origin` bilinçli olarak verilmez**, verilseydi oyun ana sayfayı script'leyip onun ağ erişimiyle CSP'yi baypas edebilirdi | `test_library.py` (sunum izin listesi) + tarayıcıda elle doğrulama |
| T3 | Prompt injection | Savunma yapısaldır, tespite dayalı değil: görev metni **veri** olarak sınırlandırılmış blok içinde iletilir, sınırlayıcıyı taklit eden içerik etkisizleştirilir, kontrol ve görünmez karakterler (sıfır genişlikli, yön değiştiren) temizlenir, karakter sınırı uygulanır, prompt'lar çalışma anında değiştirilemez. Hata mesajları görev metnini yankılamaz | `test_security.py` (T3 bölümü, 9 test) |
| T4 | **Sahte KABUL** | Denetleyicinin kararı **yapısal JSON** olarak ayrıştırılır. Serbest metin içinde geçen "KABUL" kelimesi karar sayılmaz — üretilen kodun içindeki bir yorum satırı sistemi kandıramaz. Olay seçimi `event_for_review()` üzerinden yapılır | `test_reviewer_parsing.py` |
| T4b | **Sahte test kanıtı** | Üretilen kod `console.log('# pass 99')` yazarak TAP özetini taklit edebilir. İki bağımsız önlem: ayrıştırıcı **son** özet satırını alır (gerçek özet çıktının sonundadır) ve **çıkış kodu** ayrıca kontrol edilir — çıkış kodu enjekte edilemez | `test_sandbox.py::test_sahte_ozet_test_kosucusunu_da_kandiramaz` |
| T5 | Sır sızıntısı | Üretilen kod ve transkript on yaygın anahtar desenine karşı taranır; bulgu varsa KABUL geçersizdir (G6s) ve metin maskelenir. **Görev metnindeki anahtar görevi hiç başlatmaz** — aksi hâlde transkripte ve sağlayıcıya giderdi. Bulgular sırrın kendisini taşımaz | `test_security.py` (T5 bölümü, 11 test) |
| T6 | Maliyet/DoS | §5'teki tüm limitler; ayrıca ilerleme-yok tespiti | `test_limits.py` |
| T7 | API anahtarı sızıntısı | Anahtarlar ortam değişkeninden veya arayüzden alınır; **asla diske, transkripte veya loga yazılmaz**, `.env` `.gitignore`'dadır, alt sürece geçirilmez | `test_key_vault.py` |
| T8 | **Kullanıcının emanet ettiği anahtarın dışarı çıkması** | Bkz. §3.3 "Rol bazlı anahtar girişi". Kasa yalnızca maskeli parmak izi döndürür; `redact()` bilinen anahtarları **birebir dize eşleşmesiyle** metinden siler; `SecretStr` ve özel `__repr__` istisna izlerinde sızıntıyı kapatır; hata mesajları anahtarı yankılamaz | `test_key_vault.py` (25 test) |

### Bilinen sınırlar — dürüstçe belgelenmiştir

Aşağıdakiler kapatılmamış açıklardır. Gizlenmeleri yerine, sonuçlarıyla birlikte yazılmaları tercih edilmiştir; `docs/teknik.md` içinde de yer alacaklardır.

| # | Sınır | Sonuç | Neden kabul edildi / azaltıcı faktör |
|---|---|---|---|
| S1 | **Test alt süreci için ağ ad alanı izolasyonu yoktur** | Konteynerin ağ erişimi vardır (LLM API'sine gitmesi gerekir) ve alt süreç bunu miras alır. Ayrı ağ ad alanı, ayrı konteyner gerektirirdi | Docker içinde Docker bilinçli olarak reddedildi (§3.3). Telafi: **statik içe aktarma izin listesi** — ağ modülü kullanan kod çalıştırılmadan reddedilir (T2b). Ayrıca üretilen oyun mantığı saf hesaplamadır; ağa meşru ihtiyacı yoktur |
| S2 | Statik içe aktarma denetimi desen tabanlıdır | Yeterince gizlenmiş kod (dize birleştirmeyle modül adı üretme gibi) teoride denetimi atlatabilir | Dinamik `require`/`import()` biçimleri de topluca reddedilerek gizleme yüzeyi daraltıldı. Atlatılsa dahi kod hâlâ ayrıcalıksız kullanıcı, rlimit ve konteyner sınırı içindedir — tek katman değil, **son katman** delinmiş olur |
| S3 | Sır taraması desen tabanlıdır | Bilinmeyen formatta bir anahtar yakalanmayabilir | 3 günlük kapsamda entropi tabanlı tarama kapsam dışı bırakıldı. API anahtarları alt sürece hiçbir zaman geçirilmez (ortam temizliği), dolayısıyla üretilen kodun sızdıracak bir anahtarı yoktur |
| S4 | Konteyner kaçışı bu projenin tehdit modeli dışındadır | Docker'ın kendi izolasyonundaki bir zafiyet varsayılmamıştır | Konteyner sınırı en dış katmandır; onun ötesi platform sorumluluğudur |
| S6 | **Sunum katmanı (`game.html`) hiçbir katman tarafından doğrulanmaz** | Mantık doğru olduğu hâlde oyun kullanıcıya yanlış görünebilir. **15.08'de fiilen gerçekleşti:** üretilen connect-4'te `logic.js` ve 9 test kusursuzdu, ama `game.html` içinde `{ K: '#ffeb3b', S: '#f44336' }` eşlemesi tersti — kırmızının sırasında sarı taş konuyor, sarı kazanınca kırmızı kazandı yazıyordu | **Boşluk kazara değil yapısaldır:** planlayıcıya kriterleri "`node:assert` ile test edilebilir" olacak şekilde yazması söyleniyor, bu da sunumla ilgili hiçbir şeyin kriter olamayacağını garantiliyor; denetleyiciye de estetiği denetlememesi söyleniyor ve renk eşlemesi estetik **gibi görünüyor**. Azaltıcı yön §10.1'de: anlamsal eşlemeler `logic.js`'e taşınırsa test edilebilir hale gelir |
| S5 | **Arayüzün önünde kimlik doğrulama yoktur** | Anahtar girildikten sonra, `localhost:8000`'e erişebilen herkes o anahtarla istek başlatabilir | Tek kullanıcılı yerel çalıştırma varsayımı (V3) gereğidir; oturum yönetimi 3 günlük kapsamda değildir (§2.2). Azaltıcı: port `127.0.0.1`'e bağlıdır, yerel ağa açık değildir; anahtar bellekte durur ve konteyner durdurulunca kaybolur; arayüzde açık **"anahtarları temizle"** eylemi vardır |

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
| `oyun` | string | ✔ | Serbest; kanonik biçime indirgenir (küçük harf, boşluk → tire). Sabit liste yoktur |
| `uygulanabilirlik` | object | ✔ | `{karar, gerekce, ozel_durum_sayisi, gerekli_ozellikler[], gercek_zamanli, harici_varlik_gerekli}`. `karar` ∈ `UYGUN` \| `UYGUN_DEGIL`; `gerekce` 10–500 karakter |
| `adimlar` | string[] | koşullu | `UYGUN` ise 2–6 adım zorunlu; `UYGUN_DEGIL` ise **boş olmalı** |
| `kabul_kriterleri` | string[] | koşullu | `UYGUN` ise en az 1 zorunlu, her biri test edilebilir ifade; `UYGUN_DEGIL` ise boş |
| `dosyalar` | string[] | koşullu | `UYGUN` ise en az 1; `UYGUN_DEGIL` ise boş |

**İş kuralı — değerlendirme tutarlılığı:** `karar = UYGUN` iken `ozel_durum_sayisi > 10` **veya** `harici_varlik_gerekli = true` ise sistem kararı geçersiz sayar ve `UYGUN_DEGIL` olarak işler. §7.4'teki denetleyici kuralının eşleniğidir: **planlayıcı da kendi ölçümüyle çelişemez.** İki geçersiz kılma nedeni de mevcut kapsam kurallarından türetilmiştir (U2 ve §2.2), yeni kural değildir.

**İçerik ya plandır ya rettir.** İkisinin ortası şema düzeyinde reddedilir: `UYGUN_DEGIL` kararıyla adım/kriter/dosya taşıyan bir çıktı geçersizdir.

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
| `bulgular` | object[] | ✔ | Her biri `{dosya, sorun, onem}`; `onem` ∈ `kritik` \| `orta` \| `dusuk` (**aksansız**). `KABUL` için boş liste olabilir; **`RED` için en az 1 zorunlu** |
| `test_sonucu` | object | ✔ | `{gecen: int, kalan: int, cikti: string}` |

**İş kuralı — karar tutarlılığı:** `karar = KABUL` iken `test_sonucu.kalan > 0` ise sistem kararı geçersiz sayar ve `RED` olarak işler. Denetleyici kendi test sonucuyla çelişemez.

**İş kuralı — red eyleme dönüştürülebilir olmalı:** `RED` kararı hem boş olmayan bir `gerekce` hem **en az bir bulgu** içermek zorundadır, şema düzeyinde zorlanır. Gerekçesiz bir red revizyon turunu boşa harcar: uygulayıcı neyi düzelteceğini bilemez, denetleyici aynı gerekçeyle tekrar reddeder ve sistem ilerleme-yok tespitiyle (G11) durur.

**Orkestratör kuralı — `test_sonucu` ölçülür, beyan edilmez:** Denetleyicinin döndürdüğü `test_sonucu`, orkestratör tarafından `TestRunner`ın **fiilen ölçtüğü** değerlerle değiştirilir; karar tutarlılığı kuralı bu ölçülen değerlere göre uygulanır. Aksi hâlde T4 yeniden açılırdı: denetleyici `kalan: 0` yazarak kendi çelişki denetimini atlatabilirdi. Denetleyici prompt'u bu durumu açıkça bildirir — beyan edilen sayı kararı kurtarmaz, yalnızca çelişkiyi görünür kılar.

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

**Varsayılan tablo sağlayıcı bazlıdır, rol bazlı değil.** İlk sürümde tek bir `ROLE_DEFAULT_MODEL` tablosu vardı ve bu bir **hataydı**: yalnızca OpenAI anahtarı giren bir kullanıcı `openai` + `claude-opus-5` yapılandırması alıyor, çağrı anında patlıyordu. Model kimliği sağlayıcıya ait bir şeydir, role değil.

OpenAI tarafında hesabın hangi modellere eriştiği bilinemediği için varsayılan **yedek** olarak işaretlenir (`model_kaynagi = "yedek"`) ve arayüz kullanıcıyı katalogdan seçmeye yönlendirir.

**Model seçimi — katalog.** `GET /api/modeller?saglayici=…` sağlayıcının kendi `/v1/models` ucundan canlı liste döndürür. Sabit liste tutulmaz: listedeki modeller zamanla kaybolur ve hangi modellere erişildiği hesaba göre değişir. Fiyatı bilinen modeller etikette `$5/$25 /MTok` gibi gösterilir.

**Seçim diske yazılır, anahtar yazılmaz.** Anahtar sırdır ve yalnızca bellekte durur (§3.3); model seçimi bir tercihtir ve her yeniden başlatmada yeniden sorulması gereksiz sürtünmedir. Dosya: `data/model-secimleri.json`.

**Model karar sırası:** seçim → `MODEL_<ROL>` → sağlayıcı varsayılanı. Seçim **yalnızca aynı sağlayıcı için** geçerlidir — Anthropic için seçilen model OpenAI'a gönderilemez.

**Sağlayıcı karar sırası:** **seçim** → `LLM_PROVIDER_<ROL>` → `LLM_PROVIDER` → kasada/ortamda anahtarı olan sağlayıcı → `replay`. Roller birbirinden bağımsızdır: planlayıcı Anthropic, uygulayıcı OpenAI olabilir.

**Seçim sağlayıcıyı da belirler.** İlk uygulamada seçim yalnızca modeli belirliyordu; sağlayıcı anahtarlara bakılarak seçiliyordu. Sonuç bir kısır döngüydü: `.env`'de Anthropic anahtarı olan bir kullanıcı arayüzden OpenAI seçtiğinde sağlayıcı `anthropic` kalıyor, seçim başka sağlayıcıya ait olduğu için atılıyor ve satır varsayılana dönüyordu — kullanıcıya "kaydete basınca sıfırlanıyor" olarak görünüyordu.

**Seçilen sağlayıcının anahtarı yoksa sessizce başkasına kayılmaz**; `replay`e düşülür ve gerekçe yazılır. Sessiz kayma, kullanıcının gördüğü yapılandırma ile çalışanın farklı olması demektir.

`RoleConfig` iki kaynak alanı taşır — `saglayici_kaynagi` (`secim`/`ortam`/`anahtar`/`yok`) ve `model_kaynagi` (`secim`/`ortam`/`varsayilan`/`yedek`) — arayüz her satırda bunları gösterir. Amaç, ekranda görünen yapılandırmanın gerçekten çalışan yapılandırma olduğunun kanıtlanabilir olması.

**Maliyet ayarı.** Roller bağımsız olduğu için model seçimi doğrudan bir maliyet kaldıracıdır. Ölçülen tic-tac-toe koşusundan hesaplanan örnek:

| Kurulum | Planlayıcı | Uygulayıcı | Denetleyici | Koşu başına |
|---|---|---|---|---|
| Varsayılan | Opus 5 | Sonnet 5 | Opus 5 | **$0,221** |
| Dengeli | Opus 5 | Haiku 4.5 | Sonnet 5 | **≈$0,12** |
| Ekonomik | Sonnet 5 | Haiku 4.5 | Sonnet 5 | **≈$0,08** |

Planlayıcının güçlü kalması önerilir: kabul kriterlerinin kalitesi işin geri kalanını belirler (§8.1 gerekçe sütunu).

**Yanlış yapılandırma sistemi açılmaz yapmaz.** İstenen sağlayıcının anahtarı yoksa `replay`e düşülür ve **gerekçe kaydedilir**; sağlık ucu ve arayüz her rol için bu gerekçeyi gösterir. Sessizce düşmek ile hata verip açılmamak arasındaki üçüncü yol budur.

**Token tavanı rol bazlıdır.** Uygulayıcı üç dosyanın tam içeriğini üretir (32.000), diğer roller JSON döndürür (16.000).

### 8.2 Sağlayıcı arayüzü sözleşmesi

Her sağlayıcı tek bir yöntemi uygular: bir sistem promptu, mesaj listesi ve araç tanımları alır; metin/araç çağrısı, token sayıları ve maliyeti döndürür. **Orkestratör hangi sağlayıcının çalıştığını bilmez.** Sağlayıcı değişimi tek satır yapılandırma değişikliğidir.

### 8.3 Record/replay

`replay_provider`, gerçek çağrıların istek-yanıt çiftlerini `tests/cassettes/` altına kaydeder ve tekrar oynatır. Kabul testleri **API anahtarı olmadan** çalışır.

| Konu | Karar |
|---|---|
| Kaset anahtarı | `LlmRequest.fingerprint()` — model, `max_tokens`, sistem promptu hash'i ve mesaj listesinden türetilir. **Sağlayıcıdan bağımsızdır**: aynı istek hangi sağlayıcıya giderse gitsin aynı kaseti bulur |
| Kaset eksikse | `CassetteMissing` fırlatılır. **Sahte bir yanıt uydurulmaz** — testin neyi kaçırdığı görünmeli |
| Kayıt modu | `LLM_KAYIT=1`. Kaset varsa oynatılır, yoksa gerçek çağrı yapılır ve yazılır |
| Sistem promptu | Kasete **tam metni değil hash'i** yazılır; prompt dosyaları zaten `prompts/` altında sürümlü |
| Sır güvenliği | Kaset yazılmadan önce gizleme uygulanır **ve** taranır; bulgu kalırsa kaset **yazılmaz**. Bir testi kolaylaştırmak için sır commit etmek kabul edilebilir bir takas değildir |
| **Girdi belirlenimliliği** | Denetleyicinin girdisi test çıktısını taşır; çıktıdaki süre değerleri ve göreve özgü yollar **normalleştirilir** (`test_runner.normalize_output`). Bu yapılmazsa aynı kod her koşuda farklı bir istek üretir ve kaset **asla** tutmaz |
| Kullanıcıya görünürlük | Sağlık ucu `kayitli_senaryolar` alanıyla oynatılabilir görev metinlerini döndürür; arayüz anahtarsız modda bunları tıklanabilir gösterir |

**Kayıt/oynatma yalnızca girdi belirlenimli ise çalışır.** Bu, temiz klon testinde öğrenildi: planlayıcı ve uygulayıcı kasetleri tutuyor, testler gerçekten koşuyor, ama denetleyici kaseti hiçbir zaman tutmuyordu — çünkü `node --test` çıktısındaki `duration_ms` değerleri her koşuda farklıydı. Sahte sağlayıcıyla yazılan uçtan uca testler bunu göremez; yalnızca gerçek kasetlerle yapılan bir koşu yakalayabilirdi.

### 8.4 Neden Anthropic'te SDK, OpenAI'da REST

Anthropic tarafında SDK'nın kendi soyutlamaları kullanılıyor: akış (`messages.stream()`), prompt önbelleği (`cache_control`) ve düşünme blokları. Bunları elle yeniden yazmak hem hataya açık hem gereksiz.

OpenAI tarafında bu projeden yapılan **tek bir çağrı şekli** var (sistem promptu + mesaj listesi → metin). Tek bir çağrı için büyük bir istemci bağımlılığı taşımak, imaj boyutu ve sürüm sürüklenmesi açısından karşılığını vermiyor; belgelenmiş `/v1/chat/completions` ucu `httpx` ile kullanılıyor. Ölçülen sonuç: imaj 464 MB → **438 MB**.

### 8.5 Maliyet hesabı

Maliyet `MAX_MALIYET_USD` tavanını beslediği için hesap **yukarı yuvarlanır**: bilinmeyen bir model kimliği için en pahalı bilinen fiyat kullanılır. Bilinmezliği "ücretsiz" saymak tavanı sessizce devre dışı bırakırdı. Önbellek token'ları ayrı katsayılarla girer (yazma ~1.25x, okuma ~0.1x girdi fiyatı). Sonnet 5'in tanıtım fiyatı yerine liste fiyatı yazılıdır — aynı gerekçeyle.

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

### 10.1 Test edilebilirlik sınırı — anlamsal eşlemeler nereye ait

`logic.js` test edilir, `game.html` edilmez. Bu ayrım "mantık / sunum" diye kurulmuştu ama **yanlış yerden geçiyordu**: bir işaretin hangi oyuncuyu, rengi veya etiketi temsil ettiği **sunum değil anlamdır**, ve sunum tarafında kaldığı sürece hiçbir şey onu doğrulamaz (bkz. bilinen sınır S6).

Doğru sınır şudur:

| Kategori | Nereye ait | Test edilebilir mi |
|---|---|---|
| Kural, durum, kazanma koşulu | `logic.js` | ✔ |
| **İşaret → oyuncu/renk/etiket eşlemesi** | **`logic.js`** (dışa aktarılan sabit) | ✔ |
| Çizim, ölçü, animasyon, renk **tonu** | `game.html` | ✖ — kabul edilen sınır |

Somut sonuç: `logic.js` bir eşleme dışa aktarırsa (`OYUNCULAR = { K: {ad: 'Kırmızı', renk: '#f44336'} }`) hem `game.html` oradan okur hem de eşlemenin doğruluğu `node --test` ile sınanabilir. Eşleme `game.html` içinde bir sabit olarak durduğu sürece ters yazılması hiçbir kapıdan geçmez.

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
| 2.5 | 15.08.2026 | **Dayanıklılık ve görünürlük turu.** §4.2'ye **G4r/G4e** eklendi — uygulayıcının yeniden deneme hakkı yoktu (planlayıcı ve denetleyicide vardı), asimetri ne kodda ne belgede fark edilmişti. Kesilme (`durdurma_nedeni`) JSON ayrıştırmasından **önce** tanınıyor ve bütçe büyütülerek yeniden deneniyor. `repair_json()`: katı ayrıştırma başarısız olunca yalnızca tahmin gerektirmeyen iki hatayı düzeltir; **eksik parantez tamamlanmaz**. Üç yapılandırma uyarısı koşudan önce gösteriliyor (karışık kurulum, kaset–model uyuşmazlığı) ve anahtar formunun varsayılanı "tüm roller" yapıldı. Arayüze **agent hattı görünümü**. 411 test |
| 2.4 | 15.08.2026 | **Temiz klon testi: kayıt/oynatma denetleyici adımında kırıkmış.** Sıfırdan klonlanan bir kopyada anahtarsız koşu denendi; planlayıcı ve uygulayıcı kasetleri tuttu, 12 test gerçekten koştu, ama denetleyici kaseti tutmadı. Sebep: test çıktısındaki `duration_ms` değerleri her koşuda farklı → istek farklı → parmak izi farklı. `test_runner.normalize_output()` eklendi (süre satırları ve göreve özgü yollar temizlenir, dosya adı/satır korunur). Kasetler yeniden kaydedildi. Sağlık ucuna `kayitli_senaryolar`, arayüze anahtarsız modda tıklanabilir senaryo listesi eklendi. **Temiz klonda anahtarsız olarak tic-tac-toe `KABUL_EDILDI` ve satranç `KAPSAM_DISI` doğrulandı.** 390 test |
| 2.3 | 15.08.2026 | **Seçim sağlayıcıyı da belirliyor.** v2.2'deki düzeltme yarımdı: seçim modeli belirliyor ama sağlayıcıyı belirlemiyordu, bu yüzden arayüzden OpenAI seçilip kaydedildiğinde satır varsayılana dönüyordu. Sağlayıcı karar sırasının başına **seçim** kondu; seçilen sağlayıcının anahtarı yoksa sessizce kaymak yerine `replay`e düşülüyor ve gerekçe yazılıyor. `RoleConfig.saglayici_kaynagi` eklendi, arayüz her satırda kaynak etiketi ve **sıfırla** düğmesi gösteriyor. 376 test yeşil |
| 2.2 | 15.08.2026 | **Model kataloğu + transkript geçmişi + sağlayıcı-farkında varsayılan hatası düzeltildi.** `ROLE_DEFAULT_MODEL` tek tabloydu; yalnızca OpenAI anahtarı girildiğinde `openai` + `claude-opus-5` üretiyor ve çağrı anında patlıyordu. `PROVIDER_DEFAULT_MODEL` ile sağlayıcı bazlı hale getirildi, `RoleConfig.model_kaynagi` eklendi. Yeni `llm/catalog.py` (canlı model listesi, fiyat etiketiyle) ve `llm/selection.py` (diske yazılan rol→model seçimi). Uçlar: `GET /api/modeller`, `GET|POST|DELETE /api/modeller/secim`. Arayüzde rol başına sağlayıcı+model seçimi ve **kütüphaneden transkript görüntüleme**. §8.1'e maliyet ayarı tablosu eklendi. 369 test yeşil |
| 2.1 | 15.08.2026 | **Faz 5 + sunum katmanı boşluğu.** Sohbet kutusu, **SSE ile canlı transkript**, oyun oynatıcı ve ayarlar paneli. `/api/gorev/akis` ucu eklendi. **Bilinen sınır S6 ve §10.1** yazıldı: `game.html` hiçbir kapıdan geçmiyor ve bu boşluk yapısal — insan testi connect-4'te ters renk eşlemesi buldu, 352 otomatik test bulamazdı. `Usage.fiyat_bilinen` eklendi; fiyatı bilinmeyen model kullanıldığında transkripte `maliyet_ust_sinir` sistem mesajı yazılıyor. **Yalnızca OpenAI ile koşu:** snake `KABUL_EDILDI`, tek tur, kodda sıfır değişiklik. `docker-compose.yml`'ye rol bazlı `MODEL_*` ve `LLM_PROVIDER_*` geçişleri eklendi |
| 2.0 | 15.08.2026 | **Faz 4 — sistem ilk kez uçtan uca çalıştı.** Gerçek stdio MCP sunucusu (`fs_mcp_server.py` + `mcp_client.py`), üç agent, `orchestrator/loop.py`, `orchestrator/runner.py`, `/api/gorev` uçları. **Üç gerçek koşu:** tic-tac-toe `KABUL_EDILDI` ($0.221, 12 test), connect-4 `KABUL_EDILDI` ($0.179, 9 test), satranç `KAPSAM_DISI` ($0.012, 24 özel durum sayarak). §5'e ölçülen maliyet ve token değerleri yazıldı. 352 test yeşil |
| 1.9 | 14.08.2026 | **Faz 3 — sağlayıcı katmanı.** `provider.py` (sözleşme + istek parmak izi), `pricing.py`, `factory.py` (rol bazlı çözümleme), Anthropic (SDK: akış + prompt önbelleği + uyarlanabilir düşünme), OpenAI (REST), Ollama, `replay_provider` (kayıt/oynatma). §8.1'e rol bazlı karar sırası, §8.3'e kaset kararları, **§8.4 (SDK vs REST gerekçesi)** ve **§8.5 (maliyet yukarı yuvarlanır)** eklendi. `openai` SDK'sı bağımlılıklardan çıkarıldı — imaj 464 → 438 MB. Anahtar uçları (`/api/anahtarlar`) bağlandı; `sistem` rolünün anahtar alamayacağı kasa katmanında zorlandı. 315 test yeşil |
| 1.8 | 14.08.2026 | **U4 daraltıldı + oyun kütüphanesi.** U4 ölçütü "harici varlık" değil **"harici varlık dosyası"** olarak yeniden yazıldı: kodla üretilen görsel (canvas) ve ses (Web Audio osilatörü) kapsam içidir. Bu ayrım olmadan flappy bird gibi kapsam içi olması gereken oyunlar yalnızca tıklama sesi yüzünden reddedilirdi. §2.1'e oyun kütüphanesi eklendi: her görev kendi dizininde kalır, üretilen oyunlar listelenir ve aralarında geçiş yapılır; liste ayrı bir indeksten değil transkriptlerden türetilir. §6'ya **T2c (tarayıcıda çalışan üretilmiş kod)** eklendi — süreç sandbox'ı tarayıcıyı kapsamaz, kısıt CSP ve iframe sandbox'ı ile kurulur. 264 test yeşil |
| 1.7 | 14.08.2026 | **Prompt–şema uyumu.** İnsan tarafından yazılan `prompts/*.v1.md` ile kodun zorladığı şemalar karşılaştırıldı ve dört sapma bulundu (ayrıntı: AI günlüğü Kayıt 2.2). §7.4'e iki iş kuralı eklendi: `RED` en az bir bulgu içermelidir (şema düzeyinde zorlanır) ve **`test_sonucu` orkestratör tarafından ölçülen değerlerle değiştirilir** — beyan edilen sayı karar denetimini atlatamaz. `onem` değerlerinin aksansız yazıldığı vurgulandı. Yeni test dosyası `test_prompt_ornekleri.py`: prompt'lardaki her JSON örneği gerçek şemaya karşı doğrulanıyor, sapma artık sessizce oluşamaz. 236 test yeşil |
| 1.6 | 14.08.2026 | **Faz 2 — sandbox ve güvenlik uygulandı.** `path_guard`, `secret_scan`, `input_guard`, `import_guard`, `launcher`, `process_runner`, `test_runner`. §3.3'e iki tasarım notu: fırlatıcı süreç (`preexec_fn` kilitlenme riski nedeniyle kullanılmadı) ve erişim devri. §6'ya tehdit **T4b (sahte test kanıtı)** eklendi — TAP özeti enjeksiyonu, son-eşleşme ayrıştırma + çıkış kodu ile iki bağımsız önlemle kapatıldı. Tehdit tablosundaki test sütunları gerçek test adlarıyla dolduruldu. 221 test yeşil |
| 1.5 | 14.08.2026 | **Kapsam ölçüte bağlandı + rol bazlı anahtar girişi.** §2.1.1 uygulanabilirlik ölçütü (U1–U5) eklendi; `oyun` alanı sabit enum olmaktan çıkıp serbest ada dönüştü ve §7.2'ye `uygulanabilirlik` nesnesi ile "planlayıcı kendi ölçümüyle çelişemez" iş kuralı geldi. Yeni son durum `KAPSAM_DISI` ve geçiş G2k — gerekçeli ret artık teknik hatadan ayrı. Satırancın kapsam dışılığı isim yasağı olmaktan çıkıp U2 ölçütünün sonucu oldu. §3.3'e "Rol bazlı anahtar girişi", §6'ya tehdit T8 ve bilinen sınır S5 eklendi; konteyner portu `127.0.0.1`'e bağlandı. 141 test yeşil |
| 1.4 | 14.08.2026 | **Faz 1 — uygulamadan geri beslenen spesifikasyon boşlukları.** §4.2'ye üç geçiş eklendi: G3r ve G9r (tabloda "2. kez" denen yeniden deneme haklarının 1. kez dalları yazılı değildi), G6s (KK-06'daki "sır bulunursa KABUL geçersiz" dalı tabloda yoktu). §4.2'ye `event_for_review()` kuralı, §7.1'e köken alanlarının rol bazlı zorunluluğu, §7.3'e `arac_cagrilari` iç şeması eklendi. 95 test yeşil |
| 1.3 | 14.08.2026 | **Ölçüm düzeltmesi (Faz 0).** Docker Desktop/WSL2 altında yapılan ölçüm, `RLIMIT_AS`'in Node için yanlış kaldıraç olduğunu gösterdi — 512 MB'de meşru kod bile çöküyor. Bellek tavanı `RLIMIT_DATA`ya çevrildi; §3.3'e gerekçe ve ölçüm referansı, §5'e not eklendi, §6/T2 güncellendi. Ölçüm betiği: `tests/manual/rlimit_olcumu.py`. Diğer üç rlimit, ayrıcalık düşürme ve duvar saati doğrulandı |
| 1.2 | 14.08.2026 | **Docker içinde Docker kaldırıldı.** Tek konteyner, tek imaj (Python + Node); Docker soketi bağlanmıyor, uygulama konteyner başlatmıyor. Sandbox artık süreç düzeyinde katmanlı izolasyon: ayrıcalık düşürme, rlimit'ler, zaman aşımı, yol kısıtı, ortam temizliği ve yeni **statik içe aktarma izin listesi** (T2b). §6 bilinen sınırlar tablosu baştan yazıldı — eski S1 (soket ayrıcalığı) ve S2 (yedek mod) ortadan kalktı; yerine ağ ad alanı izolasyonunun yokluğu (S1) ve desen tabanlı denetimin sınırı (S2) geldi. §5'e rlimit değerleri eklendi |
