# Teknik Doküman — Agent Oyun Atölyesi

> **Sürüm:** 1.0 · **Tarih:** 15 Ağustos 2026 · **Yazan:** Ümit İsmen
> **Kaynak kod:** `src/` · **Testler:** 352 · **Kapsam:** Proje 1, Agent-to-Agent

Bu belge sistemin **nasıl çalıştığını** anlatır. Gereksinimler ve kabul kriterleri [`analiz.md`](analiz.md), tasarım kararlarının gerekçeleri [`../PROJECT.md`](../PROJECT.md), karar sahipliği ve denetim kaydı [`ai-gunlugu.md`](ai-gunlugu.md) içindedir.

---

## 1. Mimari

### 1.1 Genel görünüm

```
        Host makine — kurulu olması gereken tek şey: Docker
        ┌──────────────────────────────────────────────────────┐
        │  tarayıcı ──► 127.0.0.1:8000                         │
        │  ┌────────────────────────────────────────────────┐  │
        │  │  TEK KONTEYNER (python:3.11-slim + node 20)    │  │
        │  │                                                │  │
        │  │   web ──► orchestrator ──► agents ──► llm      │  │
        │  │            │                  │                │  │
        │  │            │                  ▼                │  │
        │  │            │            tools ──► MCP sunucusu │  │
        │  │            │                     (alt süreç)   │  │
        │  │            ▼                                   │  │
        │  │        sandbox ──► fırlatıcı ──► node --test   │  │
        │  │                     (runner, rlimit'li)        │  │
        │  └──────────────────┬─────────────────────────────┘  │
        │                     ▼ volume: ./workspaces/          │
        └──────────────────────────────────────────────────────┘
```

**Docker içinde Docker yoktur.** Uygulama konteyner başlatmaz, Docker soketi bağlanmaz. İzolasyon süreç düzeyinde, konteyner sınırının içinde kurulur.

### 1.2 Katmanlar ve bağımlılık yönü

| Katman | Sorumluluk | Bilmediği şey |
|---|---|---|
| `web/` | HTTP, SSE akışı, tek sayfa arayüz | Orkestrasyon iç detayları |
| `orchestrator/` | Durum makinesi, tur döngüsü, limitler | Hangi LLM'in kullanıldığı |
| `agents/` | Rol davranışı, prompt yükleme, çıktı ayrıştırma | Turların nasıl sıralandığı |
| `llm/` | Sağlayıcı arayüzü ve uygulamaları | Agent rollerini |
| `tools/` | MCP istemcisi, test koşucusu | Kimin çağırdığını |
| `sandbox/` | İzolasyon, kaynak limitleri, statik denetim | Çalıştırdığı kodun ne olduğunu |
| `transcript/` | Olay kaydı, kalıcılık, kütüphane | İş mantığını |
| `security/` | Yol koruması, sır taraması, girdi sınırlama, anahtar kasası | — |

**Bağımlılık tek yönlüdür:** `web → orchestrator → agents → {llm, tools} → sandbox`. `security` ve `transcript` her katmandan çağrılabilir; kendileri yukarı doğru bağımlılık taşımaz.

### 1.3 Ana akış

```
görev metni
   │ input_guard: sınırla, görünmez karakterleri temizle, sır tara
   ▼
PLANLANIYOR ──► planlayıcı ──► uygulanabilirlik değerlendirmesi
   │                              │
   │                              └── UYGUN_DEGIL ──► KAPSAM_DISI (gerekçeli ret)
   ▼ UYGUN
UYGULANIYOR ──► uygulayıcı ──► MCP: dosya_yaz ×3
   │                              │ yol ihlali ──► HATA
   ▼
   import_guard: statik içe aktarma denetimi   ← ÇALIŞTIRMADAN ÖNCE
   │  ihlal ──► kritik bulgu, kod hiç çalıştırılmaz
   ▼
   sandbox: node --test (runner, rlimit, 30 sn)
   ▼
DENETLENIYOR ──► denetleyici ──► karar (yapısal JSON)
   │                              │ test_sonucu ÖLÇÜLEN değerle değiştirilir
   ├── KABUL + sır taraması temiz ──► KABUL_EDILDI
   ├── KABUL + sır bulundu ──────────► REDDEDILDI
   └── RED ──► REDDEDILDI ──► revizyon turu │ aynı gerekçe 2× ──► LIMIT_ASILDI
```

Sıra bağlayıcıdır: **statik denetim testten önce** (reddedilen kod hiç çalışmamalı), **test denetleyiciden önce** (kararı ölçülen sonuçla karşılaştıracağız).

---

## 2. Durum makinesi

8 durum, 16 geçiş. Tam tablo `PROJECT.md` §4.2'dedir; burada özet:

| Durum | Son mu | Anlamı |
|---|---|---|
| `PLANLANIYOR` | — | Planlayıcı görevi bölüyor |
| `UYGULANIYOR` | — | Uygulayıcı dosya yazıyor |
| `DENETLENIYOR` | — | Test koşuldu, denetleyici inceliyor |
| `REDDEDILDI` | — | Geçici; revizyon kararı veriliyor |
| `KABUL_EDILDI` | ✔ | Teslim hazır |
| `KAPSAM_DISI` | ✔ | Uygulanabilirlik ölçütü geçilemedi — **hata değil** |
| `LIMIT_ASILDI` | ✔ | Tur/token/süre/maliyet tavanı veya ilerleme yok |
| `HATA` | ✔ | Kurtarılamayan teknik hata |

**Durum makinesi saftır:** LLM çağrısı, disk erişimi ve saat okuması içermez. Yan etkiler `orchestrator/loop.py`'de yaşar. Bu ayrım sayesinde 16 geçişin tamamı 47 birim testiyle, saniyenin altında, deterministik sınanır.

`KAPSAM_DISI`'nin ayrı bir durum olması bilinçlidir: "sistem çöktü" ile "sistem değerlendirdi ve yapmadı" karışmamalı.

---

## 3. Veri modeli

### 3.1 Mesaj zarfı

Her transkript kaydı `AgentMessage`'dır:

| Alan | Tip | İş kuralı |
|---|---|---|
| `id` | UUID4 | Sistem üretir |
| `tur` | int | 1'den başlar, revizyon çevriminde artar |
| `rol` | enum | `planlayici` \| `uygulayici` \| `denetleyici` \| `sistem` |
| `zaman` | ISO-8601 UTC | Sistem üretir, UTC'ye normalize edilir |
| `icerik` | object | Şeması `rol`'e göre; uyuşmazlık reddedilir |
| `prompt_surumu` | string | Örn. `planner.v1` |
| `prompt_hash` | sha256[:12] | Prompt dosyasının içerik hash'i |
| `model` | string | Örn. `claude-opus-5` |
| `token_girdi` / `token_cikti` | int ≥ 0 | |
| `maliyet_usd` | decimal(8,5) | Sağlayıcı fiyatından hesaplanır |

**Köken alanları agent rolleri için zorunludur.** `prompt_surumu`, `prompt_hash` ve `model` olmadan bir agent mesajı transkripte giremez — bir çıktının hangi talimattan geldiği sonradan kanıtlanabilmeli. `sistem` mesajlarının promptu olmadığından bu alanlar onlarda boştur.

### 3.2 Rol içerikleri

**Planlayıcı** — `{oyun, uygulanabilirlik, adimlar[], kabul_kriterleri[], dosyalar[]}`
İçerik ya bir plandır ya bir rettir; ortası şema düzeyinde reddedilir.

**Uygulayıcı** — `{yazilan_dosyalar[], arac_cagrilari[], not}`
LLM'in çıktısı bu **değildir**: model dosya içeriklerini döndürür, bu kayıt dosyalar MCP üzerinden **yazıldıktan sonra** üretilir. Transkript "model ne dedi"yi değil **"fiilen ne oldu"yu** kaydeder.

**Denetleyici** — `{karar, gerekce, bulgular[], test_sonucu}`

### 3.3 İki iş kuralı — agent kendi ölçümüyle çelişemez

| Kural | Uygulama |
|---|---|
| `karar = KABUL` iken `test_sonucu.kalan > 0` | Karar `RED` sayılır |
| `karar = UYGUN` iken `ozel_durum_sayisi > 10` veya `harici_varlik_gerekli` | Değerlendirme `UYGUN_DEGIL` sayılır |

Ayrıca `RED` kararı **en az bir bulgu** içermek zorundadır: gerekçesiz bir red revizyon turunu boşa harcar.

### 3.4 Transkript ve kütüphane

Transkript görev metnini, zaman damgalarını, son durumu, sağlayıcı ve model eşlemesini, **tüm prompt sürüm hash'lerini**, mesajları ve son raporu taşır. JSON ve Markdown olarak dışa aktarılır.

Her görev kendi dizinindedir: `workspaces/<gorev_id>/`. Kimlik `20260815-103817-tic-tac-toe` biçimindedir — zaman öneki kronolojik sıralar, ad eki dosya sisteminde okunabilir kılar.

**Ayrı bir indeks dosyası tutulmaz.** Oyun listesi her görevin `transkript.json`'ından türetilir; iki kayıt olsaydı sapabilirlerdi.

---

## 4. API sözleşmesi

| Yöntem | Yol | İşlev |
|---|---|---|
| `GET` | `/` | Tek sayfa arayüz |
| `GET` | `/api/health` | Durum, rol yapılandırması, limitler, kaset sayısı |
| `POST` | `/api/gorev` | Görev başlatır `{gorev}` → hemen döner, koşu arka planda |
| `GET` | `/api/gorev` | Koşu durumu ve biriken mesajlar |
| `GET` | `/api/gorev/akis` | **SSE** — `mesaj`, `bitti`, `ping` olayları |
| `GET` | `/api/anahtarlar` | Maskeli parmak izleri |
| `POST` | `/api/anahtarlar` | `{rol, saglayici, anahtar}` → maskeli parmak izi |
| `DELETE` | `/api/anahtarlar` | Kasayı temizler (`?rol=` ile tek rol) |
| `GET` | `/api/modeller` | `?saglayici=…` — sağlayıcının canlı model kataloğu |
| `GET` | `/api/modeller/secim` | Kayıtlı rol→model seçimleri |
| `POST` | `/api/modeller/secim` | `{rol, saglayici, model}` |
| `DELETE` | `/api/modeller/secim` | Seçimi kaldırır (`?rol=` ile tek rol) |
| `GET` | `/api/oyunlar` | Üretilmiş oyunlar, en yeniden eskiye |
| `GET` | `/api/oyunlar/{id}` | Tek kayıt |
| `DELETE` | `/api/oyunlar/{id}` | Görevi siler |
| `GET` | `/oyun/{id}/{dosya}` | Oyun dosyası — izin listeli, CSP başlıklı |

**Eşzamanlılık:** aynı anda tek görev. İkinci istek `409` alır ve sıraya **alınmaz** — sıraya almak kullanıcıya bitmiş gibi görünen ama dakikalarca bekleyen bir iş bırakırdı.

**Anahtar uçları hiçbir koşulda anahtarı geri döndürmez.** Yanıt yalnızca `{rol, saglayici, maske, uzunluk, kaynak}` taşır ve `Cache-Control: no-store` ile işaretlenir.

---

## 5. Sağlayıcı katmanı

### 5.1 Rol–model kararı

| Rol | Varsayılan model | Gerekçe |
|---|---|---|
| Planlayıcı | `claude-opus-5` | Plan ve kabul kriteri kalitesi işin geri kalanını belirler |
| Uygulayıcı | `claude-sonnet-5` | Token'ın çoğunu bu rol harcar; en iyi maliyet/kalite dengesi |
| Denetleyici | `claude-opus-5` | Red kararının isabetli olması sistemin ana döngüsüdür |
| Çevrimdışı | Ollama | Ağ/kota bağımsız yedek, sıfır maliyet |
| Test | `replay` | Kayıtlı yanıtlar; deterministik, API'siz |

Bu tablo **varsayılandır**; her rol arayüzden ayrı ayrı değiştirilebilir.

**Karar sırası — sağlayıcı:** kullanıcı seçimi → `LLM_PROVIDER_<ROL>` → `LLM_PROVIDER` → anahtarı olan sağlayıcı → `replay`.
**Karar sırası — model:** kullanıcı seçimi → `MODEL_<ROL>` → sağlayıcı varsayılanı.

Seçimin en başta olması bir düzeltmedir: önceki sürümde seçim yalnızca modeli belirliyor, sağlayıcı anahtarlara bakılarak seçiliyordu; sonuç, arayüzden yapılan seçimin sessizce atılmasıydı.

**Varsayılan model tablosu sağlayıcı bazlıdır**, rol bazlı değil. Tek bir tablo tutmak, yalnızca OpenAI anahtarı olan bir kullanıcıya `openai` + `claude-opus-5` yapılandırması üretiyordu.

**Yanlış yapılandırma sistemi açılmaz yapmaz.** İstenen sağlayıcının anahtarı yoksa `replay`'e düşülür ve **gerekçe kaydedilir**. Sessizce başka bir sağlayıcıya kayılmaz: ekranda görünen yapılandırma ile fiilen çalışan aynı olmalıdır. `RoleConfig` iki kaynak alanı taşır (`saglayici_kaynagi`, `model_kaynagi`) ve arayüz bunları her satırda gösterir.

### 5.1.1 Model kataloğu

`GET /api/modeller?saglayici=…` sağlayıcının kendi `/v1/models` ucundan **canlı** liste döndürür. Sabit liste tutulmaz: modeller zamanla kaybolur ve hangilerine erişildiği hesaba göre değişir. Sohbet dışı modeller (görsel, ses, gömme, transkripsiyon) elenir; fiyatı bilinenler etikette gösterilir (`Claude Sonnet 5 · $3/$15 /MTok`). Sonuçlar 15 dakika bellekte önbelleğe alınır.

Seçim `data/model-secimleri.json` dosyasına yazılır. **Bilinçli asimetri:** anahtar sırdır ve yalnızca bellekte durur; model seçimi tercihtir ve yeniden başlatmayı aşar.

### 5.1.2 Maliyet ayarı

Roller bağımsız olduğu için model seçimi doğrudan bir maliyet kaldıracıdır. Ölçülen tic-tac-toe koşusundan:

| Kurulum | Planlayıcı | Uygulayıcı | Denetleyici | Koşu başına |
|---|---|---|---|---|
| Varsayılan | Opus 5 | Sonnet 5 | Opus 5 | $0,221 |
| Dengeli | Opus 5 | Haiku 4.5 | Sonnet 5 | ≈$0,12 |
| Ekonomik | Sonnet 5 | Haiku 4.5 | Sonnet 5 | ≈$0,08 |

Planlayıcının güçlü kalması önerilir: kabul kriterlerinin kalitesi işin geri kalanını belirler. Kısmanın ucuz yeri uygulayıcıdır.

### 5.2 Anthropic'te SDK, OpenAI'da REST

Anthropic tarafında SDK'nın soyutlamaları fiilen kullanılıyor: akış (`messages.stream()`), prompt önbelleği (`cache_control`), uyarlanabilir düşünme. OpenAI tarafında bu projeden yapılan tek bir çağrı şekli var; tek çağrı için büyük bir istemci bağımlılığı taşımanın karşılığı yok. Ölçülen sonuç: imaj **464 → 438 MB**.

### 5.3 Kayıt/oynatma

Gerçek çağrılar `tests/cassettes/` altına kaydedilir ve tekrar oynatılır. Kaset anahtarı istek parmak izidir (model, `max_tokens`, sistem promptu hash'i, mesajlar) ve **sağlayıcıdan bağımsızdır**.

Kaset eksikse `CassetteMissing` fırlatılır — sahte yanıt uydurulmaz. Kasetler yazılmadan önce sır taramasından geçer; bulgu kalırsa kaset **yazılmaz**.

### 5.4 Maliyet

Maliyet harcama tavanını beslediği için hesap **yukarı yuvarlanır**: bilinmeyen bir model kimliği için en pahalı bilinen tarife kullanılır. Bilinmezliği "ücretsiz" saymak tavanı sessizce devre dışı bırakırdı.

Bunun bedeli, fiyatı bilinmeyen modellerde şişik bir rakam. Bu yüzden `Usage.fiyat_bilinen` alanı var ve transkripte `maliyet_ust_sinir` sistem mesajı yazılıyor — rakam kesin bir değermiş gibi sunulmaz.

### 5.5 LLM çıktısının dayanıklılığı

Üç agent da yapısal JSON döndürür ve modeller bunu üç şekilde bozar. Her biri farklı ele alınır:

| Sorun | Tanıma | Yanıt |
|---|---|---|
| **Kesilme** — token tavanına takılma | `durdurma_nedeni` ∈ {`max_tokens`, `length`}; JSON ayrıştırmasından **önce** kontrol edilir | Bütçe 1.5 kat büyütülür (tavan 64.000), modele **daha kısa yaz** denir, bir kez yeniden denenir (G4r) |
| **Bozuk JSON** — kaçışsız satır sonu, fazladan virgül | Katı ayrıştırma başarısız | `repair_json()` tek geçişte onarır; transkripte `json_onarildi` yazılır |
| **Şema uyumsuzluğu** | Pydantic doğrulaması | Hata modele geri verilir, bir kez yeniden denenir |

**Onarımın yapmadıkları, yaptıklarından önemlidir.** Tırnak türü değiştirme, yorum silme ve **eksik parantez tamamlama** bilinçli olarak dışarıda bırakılmıştır. Sonuncusu en cazip olanıdır: kesilmiş bir JSON'u kapatmak koşuyu "kurtarır" ama kurtardığı şey yarım bir dosyadır — sistem onu geçerli sayar, testler koşar, bozuk çıktı sessizce "başarılı" olur. `test_agent_base.py` içindeki 17 testin yarısı bu sınırı sınar.

---

## 6. Güvenlik

### 6.1 Sandbox — süreç düzeyinde katmanlı izolasyon

| Katman | Uygulama | Engellediği |
|---|---|---|
| Statik içe aktarma denetimi | **Çalıştırmadan önce** izin listesi | Ağ, süreç, dosya sistemi erişimi |
| Ayrıcalık düşürme | Ayrıcalıksız `runner` kullanıcısı | Konteyner içi geniş erişim |
| `RLIMIT_CPU` | 25 sn | Sonsuz döngü |
| `RLIMIT_DATA` | 512 MB | Bellek tüketimi |
| `RLIMIT_NPROC` | 32 | Fork bombası |
| `RLIMIT_FSIZE` | 10 MB | Disk doldurma |
| Duvar saati | 30 sn → süreç grubuna `SIGKILL` | Askıda kalan süreç |
| Yol kısıtı | Kanonikleştirme + kök doğrulaması | Workspace dışına erişim |
| Ortam temizliği | Yalnızca `PATH`, `HOME`, `LANG`, `NODE_ENV` | Anahtar sızıntısı |
| Çıktı tavanı | 64 KB | Bellek doldurma |

**Bellek tavanı `RLIMIT_DATA`, `RLIMIT_AS` değil.** V8, pointer-compression için devasa bir *sanal* adres alanı ayırır ve `RLIMIT_AS` onu sayar; ölçüm `RLIMIT_AS=512 MB` altında meşru bir "hello world"ün bile `SIGTRAP` ile çöktüğünü gösterdi. Ölçüm betiği: `tests/manual/rlimit_olcumu.py`.

**Fırlatıcı süreci kullanılır, `preexec_fn` değil.** `preexec_fn` `fork` ile `exec` arasında çalışır ve çok iş parçacıklı bir süreçte kilitlenme riski taşır. Fırlatıcı normal bir alt süreçtir; limitleri kendi üzerine uygular ve `exec` ile hedefe devreder.

### 6.2 Statik içe aktarma denetimi

İzin listesi yaklaşımı: yalnızca `node:test`, `node:assert`, `node:assert/strict` ve göreli yollar geçer. Ayrıca dinamik `require`/`import`, `eval`, `new Function`, `fetch`, `XMLHttpRequest`, `process.env`, `process.binding`, `process.dlopen`, `WebAssembly` reddedilir.

Red, denetleyiciye **kritik bulgu** olarak iletilir ve kod hiç çalıştırılmaz.

### 6.3 Anahtar kasası

| Kural | Uygulama |
|---|---|
| Diske yazılmaz | Yalnızca süreç belleğinde; konteyner durunca kaybolur |
| Geri okunamaz | Dışarıya sadece `••••9f3a` + uzunluk + sağlayıcı |
| Log'a giremez | `SecretStr` + kasaya özel `__repr__` |
| Metinden silinir | `redact()` **birebir dize** eşleşmesiyle |
| Hata mesajı yankılamaz | `KeyRejected` yalnızca uzunluk/biçim söyler |
| Alt sürece geçmez | Ortam temizliği; kasa `os.environ`'a yazmaz |
| Ağa açılmaz | Port `127.0.0.1`'e bağlı |

`redact()`'in desen değil **birebir eşleşme** kullanması önemli: anahtarın tam değeri bilindiği için, desen tabanlı sır taramasının belirsizliği kullanıcı anahtarları için geçerli değildir.

### 6.4 Tarayıcı tarafı

Üretilen oyun tarayıcıda çalışır, yani süreç sandbox'ının **dışındadır**. Kısıt sunum katmanında kurulur: `connect-src 'none'` (ağ çıkışı yok), `img-src data:` (uzak görsel URL'si de sızıntı kanalıdır), `form-action 'none'`, iframe `sandbox="allow-scripts"`.

`allow-same-origin` bilinçli olarak verilmez: verilseydi oyun ana sayfayı script'leyip onun ağ erişimiyle bu CSP'yi baypas edebilirdi.

### 6.5 Koşu öncesi yapılandırma uyarıları

Güvenlik yalnızca kötü niyete karşı değildir; **öngörülebilir başarısızlığı önceden söylemek** de aynı ailedendir. Üç durum koşu başlamadan bildirilir:

| Durum | Neden başarısız olur |
|---|---|
| Karışık kurulum (bazı roller canlı, bazıları `replay`) | Canlı agent özgün çıktı üretir, replay rolü o çıktı için kaset bulamaz |
| `replay` modunda kasetlerde olmayan model seçili | Kaset parmak izi modeli içerir; seçim değişince tüm kasetler geçersizdir |
| Anahtarın tek role uygulanması | Diğer roller sessizce `replay`'de kalır |

Üçüncüsü uyarıyla **değil varsayılanla** çözüldü: anahtar formunun rol seçicisi artık "tüm roller"de başlar. Uyarı hatayı görünür kılar; doğru varsayılan onu oluşmaz kılar.

### 6.6 Tehdit özeti

| # | Tehdit | Doğrulayan test |
|---|---|---|
| T1 | Sandbox kaçışı — yol | `test_security.py` (8 test) |
| T2 | Keyfi kod yürütme | `test_sandbox.py` (10 test, gerçek süreç) |
| T2b | Ağ üzerinden sızma | `test_security.py` (26 test) |
| T2c | Tarayıcıda çalışan üretilmiş kod | `test_library.py` + tarayıcı doğrulaması |
| T3 | Prompt injection | `test_security.py` (9 test) |
| T4 | Sahte KABUL | `test_reviewer_parsing.py` (25 test) |
| T4b | Sahte test kanıtı | `test_sandbox.py` |
| T5 | Sır sızıntısı | `test_security.py` (11 test) |
| T6 | Maliyet / DoS | `test_limits.py` (13 test) |
| T7, T8 | Anahtar sızıntısı | `test_key_vault.py` (22 test) |

---

## 7. Ölçümler

### 7.1 Gerçek koşular (15.08.2026)

| Görev | Sağlayıcı | Sonuç | Tur | Girdi/çıktı tok. | Maliyet | Süre |
|---|---|---|---|---|---|---|
| tic-tac-toe | Anthropic | `KABUL_EDILDI` | 1 | 7.377 / 6.304 | $0,221 | ~85 sn |
| connect-4 | Anthropic | `KABUL_EDILDI` | 1 | ~7.000 / ~6.000 | $0,179 | ~90 sn |
| satranç | Anthropic | `KAPSAM_DISI` | 1 | 74 / 1.040 | $0,012 | ~15 sn |
| snake | **OpenAI** (`gpt-5.4`) | `KABUL_EDILDI` | 1 | 13.141 / 5.126 | ≈$0,10 ¹ | ~40 sn |
| 2048 | Anthropic | `KABUL_EDILDI` | 1 | — | — | — |

¹ Sistem ≤$0,388 raporladı (bilinmeyen fiyat → üst sınır); kullanıcı raporuna göre gerçek ≈$0,10, yani üst sınır ~4 kat yüksek. `pricing.py`'ye tahminî bir fiyat **eklenmedi**: harcama tavanını besleyen bir tabloya doğrulanmamış sayı yazmak, bu projenin baştan beri kaçındığı hatadır.

**Toplam harcama: ≈$0,51** (beş koşu, biri gerekçeli ret).

**Dört koşunun dördü de tek turda kabul aldı.** Bu, red/revizyon döngüsünün — sistemin ana mekanizmasının — gerçek koşuda henüz gözlenmediği anlamına gelir. Mekanizma `test_loop.py` içinde uçtan uca sınanmıştır (red → revizyon → kabul, ve aynı gerekçeyle iki red → `LIMIT_ASILDI`), ancak canlı bir örneği kayıtlı değildir. Dürüst ifade: **mekanizma test edilmiştir, sahada gözlenmemiştir.**

**Sağlayıcı değişimi kodda sıfır değişiklik gerektirdi** — yalnızca iki ortam değişkeni.

**Prompt önbelleğinin etkisi ölçülebilir:** Anthropic koşusunda planlayıcının ücretli girdisi 74 token'a indi (~2.500 token'lık sistem promptu önbelleğe alındı). OpenAI'da önbellek yok; girdi 7.377 → 13.141'e çıktı.

### 7.2 Sistem ölçüleri

| Ölçü | Değer |
|---|---|
| İmaj boyutu | 438 MB |
| İlk derleme | ~1 dakika |
| Test paketi | **379 test / ~18 sn** |
| Token tüketimi (tek tur) | ~13.700 — `MAX_TOKEN_TOPLAM`'ın %9'u |
| Kaydedilmiş kaset | 10 |

Tavanlar fazlasıyla geniş ve bilinçli olarak düşürülmedi: amaçları normal kullanımı sınırlamak değil, **kontrolden çıkmış bir döngüyü durdurmak**.

---

## 8. Bilinen sınırlar

Aşağıdakiler kapatılmamış açıklardır. Gizlenmeleri yerine sonuçlarıyla birlikte yazılmışlardır.

| # | Sınır | Sonuç | Azaltıcı |
|---|---|---|---|
| S1 | Test alt süreci için ağ ad alanı izolasyonu yok | Konteynerin ağ erişimi miras alınır | Statik içe aktarma izin listesi; oyun mantığının ağa meşru ihtiyacı yok |
| S2 | Statik denetim desen tabanlı | Yeterince gizlenmiş kod teorik olarak aşabilir | Dinamik biçimler topluca reddedilir; aşılsa dahi ayrıcalık düşürme, rlimit ve konteyner sınırı devrede |
| S3 | Sır taraması desen tabanlı | Bilinmeyen formatta anahtar kaçabilir | Kullanıcı anahtarları için birebir eşleşme kullanılır; alt sürece hiç anahtar geçmez |
| S4 | Konteyner kaçışı tehdit modeli dışında | — | Platform sorumluluğu |
| S5 | Arayüzde kimlik doğrulama yok | `localhost:8000`'e erişen anahtarı kullanabilir | Port yerel ağa kapalı; anahtar bellekte; açık temizleme eylemi |
| **S6** | **`game.html` hiçbir katman tarafından doğrulanmıyor** | **Mantık doğru olduğu hâlde oyun yanlış görünebilir — 15.08'de gerçekleşti** | Anlamsal eşlemelerin `logic.js`'e taşınması (§9) |

### S6 hakkında — projenin en dürüst bulgusu

Üretilen connect-4'te `logic.js` ve 9 test kusursuzdu; `game.html` içindeki renk eşlemesi tersti. **352 otomatik testin hiçbiri bulamazdı**; beş dakikalık insan oyunu buldu.

Boşluk kazara değil yapısal: planlayıcıya kriterleri "`node:assert` ile test edilebilir" yazması söyleniyor — iyi bir kural, ama sunumla ilgili hiçbir şeyin kriter olamayacağını garantiliyor. Denetleyiciye de estetiği denetlememesi söyleniyor ve renk eşlemesi estetik *gibi görünüyor*.

**Sistemin garantisi göründüğünden dardır:** "testler geçti" ile "oyun doğru" aynı şey değildir ve bu proje ikincisini iddia etmez.

---

## 9. Bilinen sınırın çözümü — test edilebilirlik sınırı

Ayrım "mantık / sunum" değil şu olmalıdır:

| Kategori | Nereye ait | Test edilebilir |
|---|---|---|
| Kural, durum, kazanma koşulu | `logic.js` | ✔ |
| **İşaret → oyuncu/renk/etiket eşlemesi** | **`logic.js`** (dışa aktarılan sabit) | ✔ |
| Çizim, ölçü, animasyon, renk tonu | `game.html` | ✖ kabul edilen sınır |

`logic.js` bir eşleme dışa aktarırsa (`OYUNCULAR = {K:{ad:'Kırmızı', renk:'#f44336'}}`) hem `game.html` oradan okur hem de ters yazım bir testle yakalanır.

Uygulaması **prompt değişikliği** gerektirir; eğitim kuralı K4 gereği prompt'lar insan tarafından yazılır. Aday değişiklikler `analiz.md` A5'te.

---

## 10. Değişiklik kaydı

| Sürüm | Tarih | Değişiklik |
|---|---|---|
| 1.2 | 15.08.2026 | §2'ye G4r/G4e (uygulayıcı yeniden denemesi); §5.3'e kayıt/oynatmanın girdi belirlenimliliği koşulu; §5.5 JSON onarımı ve sınırları; §6.6 koşu öncesi yapılandırma uyarıları. Ölçümler ve test sayısı (411) güncellendi |
| 1.1 | 15.08.2026 | §5.1'e sağlayıcı-farkında varsayılanlar ve seçim öncelikli karar sırası; §5.1.1 model kataloğu, §5.1.2 maliyet ayarı tablosu. §4'e model seçimi uçları. §7'ye 2048 koşusu, toplam harcama ve "mekanizma test edildi, sahada gözlenmedi" notu. Test sayısı 379 |
| 1.0 | 15.08.2026 | İlk sürüm — mimari, veri modeli, API sözleşmesi, güvenlik, ölçümler, bilinen sınırlar |
