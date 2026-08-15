# Agent Oyun Atölyesi

Bir sohbet kutusuna **"snake oyunu yaz"** yazarsınız. Üç yapay zekâ agent'ı —
**planlayıcı**, **uygulayıcı**, **denetleyici** — kendi aralarında konuşarak
görevi tamamlar ve tarayıcıda oynanabilir bir oyun üretir.

Sistemin ayırt edici özelliği agent'ların konuşması değil, **birbirini
reddedebilmesidir.** Denetleyici testleri gerçekten çalıştırır, uygulayıcının
çıktısını gerekçeli olarak geri çevirir ve revizyon ister.

> GTech Yaz Akademisi bitirme projesi — Proje 1: Agent-to-Agent Geliştirme.

```
görev metni
   ▼
PLANLAYICI ──► uygulanabilirlik değerlendirmesi + test edilebilir kriterler
   │                └── ölçütü geçemezse ──► KAPSAM_DIŞI (gerekçeli ret)
   ▼
UYGULAYICI ──► MCP ile logic.js · logic.test.js · game.html
   ▼
   statik içe aktarma denetimi ──► sandbox: node --test
   ▼
DENETLEYİCİ ─► yapısal JSON ile KABUL / RED
   └── RED ──► revizyon turu ──► UYGULAYICI
```

---

## 60 saniyede deneyin — API anahtarı gerekmez

**Tek ön koşul: Docker.** Host'a Python, Node veya başka bir bağımlılık
kurulmaz; hepsi imajın içindedir.

```bash
git clone https://github.com/kaanismen/AgenticGameWorkshop.git
cd AgenticGameWorkshop
docker compose up
```

Tarayıcıdan **http://localhost:8000** — `.env` dosyası yoksa sistem `replay`
moduyla açılır ve **kayıtlı senaryoları** oynatır. Görev kutusunun altındaki
düğmelerden birine tıklayıp **üret**e basın:

| Senaryo | Ne gösterir |
|---|---|
| `tic tac toe oyunu yaz, iki oyuncu sirayla oynasin` | Mutlu senaryo — testler koşar, oyun oynanabilir |
| `satranc oyunu yaz, hamle gecerliligini kontrol etsin` | Hata senaryosu — 24 özel durum sayılarak gerekçeli ret |

Bu modda **testler gerçekten koşar** ve dosyalar gerçekten üretilir; yalnızca
LLM yanıtları kasetten gelir. Hiçbir ücret ödenmez.

### Kendi anahtarınızla

Ayarlar panelinden **her agent için ayrı** sağlayıcı ve model seçebilirsiniz;
model listesi sağlayıcınızın kendi kataloğundan canlı gelir. Anahtar yalnızca
bellekte tutulur, diske yazılmaz.

Alternatif olarak `.env`:

```bash
cp .env.example .env      # PowerShell: Copy-Item .env.example .env
docker compose up --build
```

### Testler

```bash
docker compose run --rm test
```

**390 test, ~19 saniye.** Testler de konteynerde koşar; host'a pytest kurulmaz.
Hiçbir otomatik test gerçek API çağrısı yapmaz.

---

## Ölçülen sonuçlar

| Görev | Sağlayıcı | Sonuç | Tur | Maliyet |
|---|---|---|---|---|
| tic-tac-toe | Anthropic | `KABUL_EDILDI`, 12 test geçti | 1 | $0,221 |
| connect-4 | Anthropic | `KABUL_EDILDI`, 9 test geçti | 1 | $0,179 |
| snake | OpenAI | `KABUL_EDILDI`, 5 test geçti | 1 | ≈$0,10 |
| satranç | Anthropic | `KAPSAM_DISI` — 24 özel durum | 1 | $0,012 |

Model seçimi doğrudan bir maliyet kaldıracıdır: varsayılan kurulum $0,22,
dengeli kurulum (uygulayıcı Haiku, denetleyici Sonnet) ≈$0,12.

**Kapsam bir isim listesiyle değil ölçütle belirlenir** — connect-4 gibi
listede olmayan oyunlar üretilebilir, satranç gibi kural karmaşıklığı yüksek
olanlar gerekçeyle reddedilir.

---

## Belgeler

| Dosya | İçerik |
|---|---|
| [docs/kilavuz.md](docs/kilavuz.md) | **Buradan başlayın** — kurulum, kullanım, durum açıklamaları, sorun giderme |
| [docs/analiz.md](docs/analiz.md) | Analiz dokümanı — 15 user story, 29 kabul kriteri, izlenebilirlik matrisi |
| [docs/teknik.md](docs/teknik.md) | Teknik doküman — mimari, veri modeli, API sözleşmesi, ölçümler, bilinen sınırlar |
| [docs/ai-gunlugu.md](docs/ai-gunlugu.md) | AI çalışma günlüğü — 23 kayıt, 32 kararlık kütük, 18 maddelik denetim özeti |
| [PROJECT.md](PROJECT.md) | Context paketi — geliştiricinin (ve AI aracının) çalıştığı bağlayıcı referans |
| [docs/faz-plani.md](docs/faz-plani.md) | Bağımlılık analizi ve inşa sırası |

---

## Güvenlik

AI'ın ürettiği kod **gerçekten çalıştırılır**, dolayısıyla güvenilmez kabul
edilir. İzolasyon konteyner içinde süreç düzeyinde, katmanlı kurulur:

çalıştırmadan önce statik içe aktarma denetimi · ayrıcalıksız `runner`
kullanıcısı · CPU/bellek/süreç/dosya rlimit'leri · 30 sn zaman aşımı ·
workspace dışına çıkamayan yollar · temizlenmiş ortam değişkenleri ·
tarayıcı tarafında ağ çıkışını kapatan CSP.

**Docker içinde Docker yoktur** — Docker soketi bağlanmaz.

### Bilinen sınırlar dürüstçe yazılıdır

Altı kapatılmamış sınır [`docs/teknik.md`](docs/teknik.md) §8'de sonuçlarıyla
listelenmiştir. En önemlisi:

> **`game.html` hiçbir katman tarafından doğrulanmaz.** Sistem `logic.js`'i
> testlerle güvence altına alır; arayüz katmanı otomatik bir kapıdan geçmez.
> Gerçekte yaşandı: üretilen connect-4'te mantık ve 9 testin tamamı doğruyken
> renk eşlemesi tersti. **"KABUL_EDILDI" testler geçti demektir, oyun her
> açıdan doğru demek değildir.**
