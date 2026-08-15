# Demo Senaryosu — 5 dakika

> Kayıt öncesi bu dosyayı ikinci ekranda veya telefonda açık tutun.

## Kurulum

Demo **GitHub'dan taze klonlanmış** bir kopyadan çekilir. Gerekçe: eğitmenin
göreceği şeyin birebir aynısı olur, `.env` yoktur, kütüphane boştur ve hiç
para harcanmaz.

```powershell
git clone https://github.com/kaanismen/AgenticGameWorkshop.git demo-AgenticGameWorkshop
cd demo-AgenticGameWorkshop
docker compose up -d --build
```

Tarayıcı: **http://localhost:8000**

> **Geliştirme örneği aynı portu kullanır.** Kayıttan önce onu durdurun:
> `cd "GTech Project"; docker compose down`

### Kayıt öncesi son kontrol

| Kontrol | Beklenen |
|---|---|
| Ayarlar → roller | üçü de `replay` |
| Görev kutusu altı | iki senaryo düğmesi görünüyor |
| Üretilen oyunlar | "Henüz oyun üretilmedi" |
| Tarayıcı yakınlaştırma | %100 (metin okunabilir olsun) |

### Kayıt aracı

Windows 11 **Ekran Alıntısı Aracı** (Win+Shift+S → video) bölge kaydeder,
bu demo için en pratiği. Alternatif: OBS.

**Tavsiye: kaydı yalnızca tarayıcı penceresinde tutun.** Terminali göstermek
gerekmiyor; kurulumu sesle anlatmak yeterli. Pencere değiştirmek hem kaydı
zorlaştırır hem süre yer.

---

## Akış

### 0:00 – 0:30 · Ne olduğu

> "Bir sohbet kutusuna oyun istiyorum. Üç yapay zekâ agent'ı — planlayıcı,
> uygulayıcı, denetleyici — kendi aralarında konuşup oynanabilir bir oyun
> üretiyor. Ayırt edici nokta konuşmaları değil, **birbirlerini
> reddedebilmeleri**."

Ekranda: açılış sayfası. Kayıtlı senaryo düğmelerini göster.

> "Şu an hiçbir API anahtarı girilmedi. Sistem kayıtlı senaryo modunda —
> testler gerçekten koşacak, dosyalar gerçekten üretilecek, sadece LLM
> yanıtları kasetten gelecek."

### 0:30 – 2:15 · Mutlu senaryo

`tic tac toe oyunu yaz, iki oyuncu sirayla oynasin` düğmesine tıkla → **üret**.

Transkript akarken anlat:

| Mesaj | Ne söylenecek |
|---|---|
| 🟣 planlayıcı | "Önce uygulanabilir mi diye değerlendiriyor — 2 özel durum, ölçütü geçiyor. Sonra **test edilebilir** kabul kriterleri yazıyor." |
| 🔵 uygulayıcı | "Üç dosya üretti ve bunları **MCP sunucusu üzerinden** yazdı. Ayrı süreçte çalışan gerçek bir stdio sunucusu." |
| ⚪ sistem | "Kod çalıştırılmadan önce statik denetimden geçti, sonra sandbox'ta `node --test` koştu: 12 test, hepsi geçti." |
| 🟡 denetleyici | "Kararı **yapısal JSON**. Serbest metinde geçen 'KABUL' kelimesi karar sayılmaz. Ayrıca test sonucunu denetleyici beyan etmiyor — sistem ölçüp yerine koyuyor, yani kendi denetimini atlatamıyor." |

Oyun kendiliğinden açılır. **Birkaç hamle oyna.**

> "Her mesajın başlığında hangi prompt sürümünün, hangi modelin
> kullanıldığı ve o adımın token/maliyet değeri yazıyor."

### 2:15 – 3:00 · Hata senaryosu

`satranc oyunu yaz...` düğmesine tıkla → **üret**.

> "Şimdi yapamayacağı bir şey isteyeceğim."

`KAPSAM_DISI` gelince gerekçeyi **oku**:

> "Rok, en passant, şah/mat, terfi, pat… **24 özel durum** sayıyor ve tavan
> 10. Dikkat: bu `HATA` değil, ayrı bir son durum. Sistem çökmedi —
> değerlendirdi ve gerekçesiyle reddetti."

> "Kapsam sabit bir oyun listesiyle değil **ölçütle** belirleniyor. Bu yüzden
> listede olmayan connect-4 üretilebiliyor, satranç reddediliyor."

### 3:00 – 3:45 · Denetlenebilirlik

Kütüphanede tic-tac-toe kaydının **transkript** düğmesine bas.

> "Her koşu diskte duruyor. Görev metni, hangi geçiş kuralıyla bitildiği,
> token ve maliyet, ve **prompt sürüm hash'leri** — yani bu çıktıyı hangi
> talimatın ürettiği sonradan kanıtlanabiliyor."

Reddedilen satranç kaydını da göster:

> "Başarısız koşular da listede kalıyor. Sistem hatayı saklamıyor, kaydediyor."

### 3:45 – 4:30 · Model kararları

**Ayarlar ve kurulum denetimi** panelini aç.

> "Her agent'ın sağlayıcısı ve modeli ayrı seçilebiliyor. Liste
> sağlayıcının kendi kataloğundan canlı geliyor, fiyat etiketleriyle."

> "Bu doğrudan bir maliyet kaldıracı: varsayılan kurulumda oyun başına
> 22 sent, uygulayıcıyı Haiku'ya alınca 12 sent. Ama planlayıcıyı güçlü
> bırakmak gerekiyor — kötü bir kabul kriteri, diğer ikisi ne kadar iyi
> olursa olsun kötü bir oyun üretir."

Kurulum denetimi ve limitleri kısaca göster.

### 4:30 – 5:00 · Dürüst kapanış

> "Son olarak sistemin **bilmediği** bir şey. `logic.js` testlerle güvence
> altında ama `game.html` hiçbir otomatik kapıdan geçmiyor. Üretilen bir
> connect-4'te mantık ve dokuz testin tamamı doğruyken arayüzdeki renk
> eşlemesi tersti — bunu 379 test değil, oyunu oynamak buldu."

> "Yani 'KABUL_EDILDI' testler geçti demek, oyun her açıdan doğru demek
> değil. Bu sınır teknik dokümanda S6 olarak, kılavuzda da kullanıcıya
> doğrudan yazılı."

---

## Tekrar çekim

Kütüphaneyi sıfırlamak için:

```powershell
cd demo-AgenticGameWorkshop
docker compose down
Remove-Item workspaces -Recurse -Force
docker compose up -d
```

## Demo sonrası

Geliştirme örneğine dönmek için:

```powershell
cd "GTech Project"
docker compose up -d
```

---

## Süre sıkışırsa

Kesme sırası — en az kaybettiren önce:

1. Kurulum denetimi ve limitler (3:45 bloğunun sonu)
2. Reddedilen koşunun transkripti (3:00 bloğu kısalır)
3. Oyunu oynama süresi (birkaç hamle yeter)

**Asla kesme:** denetleyicinin karar mekanizması anlatımı ve dürüst kapanış.
Rubrikteki "AI kullanım olgunluğu" kaleminin karşılığı bu ikisi.
