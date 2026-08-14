# Agent Oyun Atölyesi

Bir sohbet kutusuna **"snake oyunu yaz"** yazarsınız. Üç yapay zekâ agent'ı —
**planlayıcı**, **uygulayıcı**, **denetleyici** — kendi aralarında konuşarak
görevi tamamlar ve tarayıcıda oynanabilir bir oyun üretir.

Sistemin ayırt edici özelliği agent'ların konuşması değil, **birbirini
reddedebilmesidir.** Denetleyici testleri çalıştırır, uygulayıcının çıktısını
gerekçeli olarak geri çevirir ve revizyon ister.

> GTech Yaz Akademisi bitirme projesi — Proje 1: Agent-to-Agent Geliştirme.

---

## Çalıştırma

**Tek ön koşul: Docker.** Host'a Python, Node veya başka bir bağımlılık
kurulmaz; hepsi imajın içindedir.

```bash
docker compose up
```

Ardından tarayıcıdan: **http://localhost:8000**

### API anahtarı olmadan da çalışır

`.env` dosyası **zorunlu değildir.** Yoksa sistem `replay` sağlayıcısıyla açılır
ve kayıtlı senaryoları oynatır — anahtar girmeden sistemi uçtan uca
görebilirsiniz. Açılış sayfası hangi modda olduğunuzu ve nedenini gösterir.

Gerçek üretim için:

```bash
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
# .env içine ANTHROPIC_API_KEY veya OPENAI_API_KEY yazın
docker compose up --build
```

Ollama kullanacaksanız host makinede çalışıyor olması yeterlidir;
konteyner `host.docker.internal:11434` üzerinden erişir.

### Testler

```bash
docker compose run --rm test
```

Testler de konteynerde koşar; host'a pytest kurulmaz. Hiçbir otomatik test
gerçek API çağrısı yapmaz.

---

## Belgeler

| Dosya | İçerik |
|---|---|
| [PROJECT.md](PROJECT.md) | Context paketi: kapsam, mimari, durum makinesi, şemalar, güvenlik politikası |
| [docs/faz-plani.md](docs/faz-plani.md) | Bağımlılık analizi ve inşa sırası |
| [docs/analiz.md](docs/analiz.md) | Analiz dokümanı — user story'ler, kabul kriterleri |
| [docs/teknik.md](docs/teknik.md) | Teknik doküman — veri modeli, API sözleşmesi, bilinen sınırlar |
| [docs/kilavuz.md](docs/kilavuz.md) | Kullanım kılavuzu |
| [docs/ai-gunlugu.md](docs/ai-gunlugu.md) | AI çalışma günlüğü — prompt'lar, kararlar, denetim notları |

---

## Güvenlik özeti

AI'ın ürettiği kod **gerçekten çalıştırılır**, dolayısıyla güvenilmez kabul
edilir. İzolasyon konteyner içinde süreç düzeyinde, katmanlı kurulur:
ayrıcalıksız `runner` kullanıcısı · CPU/bellek/süreç/dosya rlimit'leri ·
30 sn zaman aşımı · workspace dışına çıkamayan yollar · çalıştırmadan önce
statik içe aktarma denetimi · temizlenmiş ortam değişkenleri.

**Docker içinde Docker yoktur** — Docker soketi bağlanmaz. Gerekçesi ve
kapatılmamış sınırlar `PROJECT.md` §6'da dürüstçe listelenmiştir.
