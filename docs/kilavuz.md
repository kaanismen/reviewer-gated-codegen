# Kullanım Kılavuzu — Agent Oyun Atölyesi

> **Sürüm:** 1.0 · **Tarih:** 15 Ağustos 2026

Bu kılavuz sistemi **sıfırdan çalıştırmak** ve kullanmak içindir. Teknik ayrıntılar [`teknik.md`](teknik.md), gereksinimler [`analiz.md`](analiz.md) içindedir.

---

## 1. Kurulum

### Ön koşul

**Docker.** Başka hiçbir şey gerekmez — Python, Node ve tüm bağımlılıklar imajın içindedir.

| İşletim sistemi | Gereken |
|---|---|
| Windows / macOS | Docker Desktop |
| Linux | Docker Engine + Compose eklentisi |

### Çalıştırma

```bash
git clone <depo-adresi>
cd gtech-agent-atolyesi
docker compose up
```

İlk derleme ~1 dakika sürer (imaj 438 MB). Ardından tarayıcıdan:

**http://localhost:8000**

> 📸 *Ekran görüntüsü 1 — açılış ekranı*

### Durdurma

```bash
docker compose down
```

Üretilen oyunlar `workspaces/` altında kalır; konteyner silinse de kaybolmazlar.

---

## 2. API anahtarı olmadan deneme

**Anahtar girmek zorunda değilsiniz.** `.env` dosyası yoksa sistem `replay` moduyla açılır ve önceden kaydedilmiş senaryoları oynatır. Ayarlar panelinde her rolün yanında `replay` yazar ve nedeni görünür:

> *"hiçbir API anahtarı tanımlı değil; kayıtlı senaryolar oynatılacak"*

Bu modda görev başlatabilir, kayıtlı bir oyunun uçtan uca üretilişini izleyebilir ve sonucu oynayabilirsiniz — hiçbir ücret ödemeden.

---

## 3. Kendi anahtarınızla çalıştırma

İki yol var.

### Yol A — arayüzden (önerilen)

**Ayarlar ve kurulum denetimi** panelini açın, her agent için ayrı anahtar girin:

| Alan | Seçenek |
|---|---|
| Rol | planlayıcı · uygulayıcı · denetleyici |
| Sağlayıcı | anthropic · openai |
| Anahtar | API anahtarınız |

> 📸 *Ekran görüntüsü 2 — ayarlar paneli, anahtar girişi ve rol tablosu*

Kaydettiğinizde yalnızca **maskeli parmak izi** görünür (`••••9f3a`). Anahtarın kendisi hiçbir yanıtta geri dönmez.

**Anahtar diske yazılmaz.** Yalnızca çalışan sürecin belleğinde durur; `docker compose down` sonrası kaybolur. Bu bir eksiklik değil, tasarımdır.

Roller birbirinden bağımsızdır: planlayıcıyı Anthropic, uygulayıcıyı OpenAI ile çalıştırabilirsiniz.

### Model seçme — maliyeti buradan düşürürsünüz

Anahtarı kaydettikten sonra her rolün yanındaki **model** açılır kutusuna tıklayın. Liste **sağlayıcınızın kendi kataloğundan** canlı gelir; fiyatı bilinen modeller etiketinde gösterilir (`Claude Sonnet 5 · $3/$15 /MTok`).

Seçtikten sonra **kaydet**. Seçim diske yazılır ve `docker compose down` sonrası da durur — anahtarların aksine.

Roller bağımsız olduğu için model seçimi doğrudan bir maliyet kaldıracıdır:

| Kurulum | Planlayıcı | Uygulayıcı | Denetleyici | Koşu başına |
|---|---|---|---|---|
| Varsayılan | Opus 5 | Sonnet 5 | Opus 5 | ~$0,22 |
| **Dengeli** | Opus 5 | **Haiku 4.5** | **Sonnet 5** | **~$0,12** |
| Ekonomik | Sonnet 5 | Haiku 4.5 | Sonnet 5 | ~$0,08 |

**Planlayıcıyı güçlü bırakın.** Kabul kriterlerinin kalitesi işin geri kalanını belirler: kötü bir kriter, uygulayıcı ve denetleyici ne kadar iyi olursa olsun kötü bir oyun üretir.

Model seçilmemiş bir sağlayıcıda rolün yanında **`yedek`** yazar — sistem tahminî bir kimlik kullanıyor demektir, katalogdan seçmeniz önerilir.

### Yol B — `.env` dosyasıyla

Kalıcı bir kurulum istiyorsanız:

```bash
cp .env.example .env      # Windows: Copy-Item .env.example .env
```

`.env` içine anahtarınızı yazın:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Sonra `docker compose up`. `.env` dosyası `.gitignore`'dadır, depoya girmez.

---

## 4. Oyun üretme

Görev kutusuna doğal dille yazın:

```
snake oyunu yaz, yılan yem yiyince uzasın ve kendine çarpınca oyun bitsin
```

**üret** düğmesine basın. Transkript canlı akmaya başlar:

> 📸 *Ekran görüntüsü 3 — canlı transkript, üç agent mesajı görünürken*

| Renk | Agent | Ne gösterir |
|---|---|---|
| 🟣 mor | planlayıcı | Uygulanabilirlik değerlendirmesi ve kabul kriterleri |
| 🔵 mavi | uygulayıcı | Yazılan dosyalar, boyutları, MCP çağrı sayısı |
| 🟡 sarı | denetleyici | KABUL/RED kararı, gerekçe, bulgular, test sonucu |
| ⚪ gri | sistem | Durum geçişleri, test koşusu, limit uyarıları |

Her mesajın başlığında hangi prompt sürümünün, hangi modelin kullanıldığı ve o adımın token/maliyet değerleri yazar.

Tipik bir koşu **40–90 saniye** sürer ve **$0,18–0,22** tutar.

Kabul edilirse oyun kendiliğinden aşağıda açılır.

---

## 5. Oyunları oynama

> 📸 *Ekran görüntüsü 4 — üretilmiş bir oyun oynanırken*

| Düğme | İşlev |
|---|---|
| **oynat** | Oyunu sayfa içinde açar |
| **tam ekran** | Tam ekran — ok tuşlu oyunlar için önerilir |
| **yeni sekmede aç** | Oyunu tek başına yeni sekmede açar |

**Ok tuşlarıyla oynanan oyunlarda:** önce oyun alanına tıklayın. Odak oyunda değilken ok tuşları sayfayı kaydırır. **Tam ekran** bu sorunu tamamen ortadan kaldırır.

Üretilen tüm oyunlar **Üretilen oyunlar** listesinde kalır; aralarında serbestçe geçiş yapabilirsiniz. Yeni bir görev öncekini silmez.

### Geçmiş transkriptleri okuma

Her kaydın yanındaki **transkript** düğmesi o koşunun tam kaydını açar:

- Görev metni, başlangıç zamanı, son durum ve hangi geçiş kuralıyla bitildiği
- Toplam tur, token ve maliyet
- **Kullanılan prompt sürümleri ve hash'leri** — hangi talimatın bu çıktıyı ürettiğinin kanıtı
- Her agent mesajı: planlayıcının kriterleri, uygulayıcının yazdığı dosyalar, denetleyicinin kararı ve bulguları

Alttaki bağlantılardan **JSON** veya **Markdown** olarak indirebilirsiniz.

Reddedilen koşular da listede kalır (`kapsam dışı`, `limit aşıldı`) — neyin neden olmadığını görmek için.

---

## 6. Durumları anlamak

Koşu bittiğinde transkriptin altında son durum yazar.

### `KABUL_EDILDI` ✅

Testler geçti, sır taraması temiz, oyun oynanabilir.

### `KAPSAM_DISI` ⚠️ — hata değil

Görev **uygulanabilirlik ölçütünü** geçemedi. Sistem çökmedi; değerlendirdi ve gerekçesiyle reddetti.

Örnek — satranç istendiğinde:

> *"U2 ihlali: altı taş türü için ayrı hamle üretimi, rok (kısa/uzun, hak kaybı, geçilen kare tehdidi), en passant, piyon terfisi, şah tehdidi altında bağlı taş kısıtı, şah/mat ve pat tespiti özel durum tavanını (10) fazlasıyla aşıyor."*

Ölçüt beş sorudan oluşur:

| # | Soru |
|---|---|
| U1 | Oyun durumu tek bir veri yapısında tutulabiliyor mu? |
| U2 | Özel durum sayısı 10 veya altında mı? |
| U3 | Kazanma koşulu saf fonksiyonla test edilebiliyor mu? |
| U4 | Harici dosya (`.png`, `.mp3`) gerekiyor mu? |
| U5 | Gerçek zamanlı animasyon gerekiyor mu? *(tek başına engel değil)* |

**Ne yapmalı:** daha basit bir oyun isteyin, veya kapsamı daraltın ("satranç" yerine "sadece kale ve şah ile basitleştirilmiş satranç").

### `LIMIT_ASILDI` ⚠️

İki nedenden biri:

| Neden | Raporda görünen |
|---|---|
| Tur/token/süre/maliyet tavanı doldu | `dolan_limit` alanı |
| **İlerleme yok** — denetleyici aynı gerekçeyle iki kez üst üste reddetti | `son_red_gerekcesi` alanı |

İkincisi bir güvenlik mekanizmasıdır: agent'lar birbirini sonsuza dek reddedip token yakmasın diye.

**Ne yapmalı:** görevi daha açık yazın, veya `MAX_TUR` değerini artırın (bkz. §7).

### `HATA` ❌

Kurtarılamayan teknik hata. Sık nedenler:

| Belirti | Sebep | Çözüm |
|---|---|---|
| `sema hatasi` | Model iki kez geçersiz JSON döndürdü | Görevi yeniden deneyin; sürerse prompt'ları gözden geçirin |
| `yol_ihlali` | Model workspace dışına yazmayı denedi | Güvenlik ihlali; MCP sunucusu engelledi, kurtarma yok |
| `ProviderAuthError` | Anahtar geçersiz veya süresi dolmuş | Ayarlar panelinden yeniden girin |
| `CassetteMissing` | `replay` modunda bu görev için kayıt yok | Anahtar girin veya kayıtlı bir görevi deneyin |

---

## 7. Ayarlar

Tüm limitler ortam değişkeniyle geçersiz kılınabilir:

```bash
MAX_TUR=2 MAX_MALIYET_USD=0.30 docker compose up
```

| Değişken | Varsayılan | İşlevi |
|---|---|---|
| `MAX_TUR` | 5 | Revizyon turu tavanı |
| `MAX_MALIYET_USD` | 1.00 | Sert harcama tavanı |
| `MAX_TOKEN_TOPLAM` | 150000 | Bağlam patlaması koruması |
| `MAX_SURE_SN` | 300 | Duvar saati |
| `LLM_PROVIDER` | *(oto)* | `anthropic` \| `openai` \| `ollama` \| `replay` |
| `MODEL_PLANLAYICI` | `claude-opus-5` | Rol bazlı model |
| `MODEL_UYGULAYICI` | `claude-sonnet-5` | |
| `MODEL_DENETLEYICI` | `claude-opus-5` | |
| `LLM_KAYIT` | *(kapalı)* | `1` → gerçek çağrıları kasede kaydet |
| `WEB_PORT` | 8000 | Host portu |

Etkin değerleri **Ayarlar → Etkin limitler** bölümünde görebilirsiniz.

---

## 8. Testleri çalıştırma

```bash
docker compose run --rm test
```

352 test, ~18 saniye. Testler de konteynerde koşar; host'a pytest kurulmaz.

**Hiçbir otomatik test gerçek API çağrısı yapmaz.**

Sandbox kaynak limitlerinin fiilen uygulandığını görmek için:

```bash
docker compose exec atolye python tests/manual/rlimit_olcumu.py
```

---

## 9. Bilinmesi gereken sınır

**Sistem `logic.js`'i doğrular, `game.html`'i doğrulamaz.**

Oyun mantığı testlerle güvence altındadır. Ancak arayüz katmanı (çizim, renk eşlemesi, tuş bağlama) hiçbir otomatik kapıdan geçmez. Gerçekte yaşanan bir örnek: üretilen connect-4'te mantık ve 9 testin tamamı doğruyken `game.html` içindeki renk eşlemesi tersti — kırmızının sırasında sarı taş konuyordu.

**Pratik sonucu:** "KABUL_EDILDI" ifadesi *testler geçti* demektir, *oyun her açıdan doğru* demek değildir. Üretilen oyunu birkaç dakika oynayın.

Ayrıntı ve çözüm önerisi: [`teknik.md`](teknik.md) §8–9.

---

## 10. Sorun giderme

| Sorun | Çözüm |
|---|---|
| `docker compose up` hata veriyor | Docker Desktop çalışıyor mu? `docker info` ile bakın |
| Sayfa açılmıyor | Port çakışması olabilir: `WEB_PORT=8080 docker compose up` |
| Roller `replay` görünüyor | Anahtar girilmemiş. Ayarlar panelinden girin veya `.env` oluşturun |
| Anahtar girdim ama hâlâ `replay` | Sağlayıcı seçimi yanlış olabilir; rol tablosundaki **gerekçe** sütunu nedeni yazar |
| Ok tuşları sayfayı kaydırıyor | Oyun alanına tıklayın veya **tam ekran**'a geçin |
| Oyun listede ama "oynat" pasif | Yalnızca `KABUL_EDILDI` durumundaki oyunlar oynanabilir |
| Koşu `409` döndürüyor | Aynı anda tek görev çalışır; bitmesini bekleyin |

---

## 11. Değişiklik kaydı

| Sürüm | Tarih | Değişiklik |
|---|---|---|
| 1.0 | 15.08.2026 | İlk sürüm — kurulum, anahtarsız deneme, anahtar girişi, oyun üretme ve oynama, durum açıklamaları, ayarlar, sorun giderme |
