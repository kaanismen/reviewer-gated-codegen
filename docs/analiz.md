# Analiz Dokümanı — Agent Oyun Atölyesi

> **Sürüm:** 1.0 · **Tarih:** 14 Ağustos 2026 · **Yazan:** Ümit İsmen (analist rolü)
> **Proje:** GTech Yaz Akademisi bitirme projesi — Proje 1, Agent-to-Agent Geliştirme

## Bu belge neyi kapsar

Bu doküman **analist A bloğunun** teslimidir: problem tanımı, paydaşlar, user story'ler, Given/When/Then kabul kriterleri, kapsam kararları, varsayımlar, kısıtlar ve izlenebilirlik matrisi.

Diğer analist blokları başka dosyalarda durur ve buradan referans verilir:

| Blok | İçerik | Nerede |
|---|---|---|
| A | User story, kabul kriteri, kapsam | **Bu belge** |
| B | Durum makinesi tablosu, alan sözlüğü | [`PROJECT.md`](../PROJECT.md) §4, §7 |
| C | Denetim raporu — AI çıktısının nerede sorgulandığı | [`docs/ai-gunlugu.md`](ai-gunlugu.md) |
| D | Güvenlik ve tehdit modeli | [`PROJECT.md`](../PROJECT.md) §6 |
| E | Context paketi — geliştiricinin çalıştığı belge | [`PROJECT.md`](../PROJECT.md) tümü |

---

## 1. Problem tanımı

Kod üreten yapay zekâ araçları yaygınlaştı, ancak çoğu **tek agent** ve **tek geçiş** çalışır: model kodu üretir, insan doğrular. Doğrulama yükü tamamen insandadır ve model kendi çıktısındaki hatayı ne fark eder ne de düzeltmek zorunda kalır.

Bu proje şunu sorar: **yapay zekâ agent'ları birbirini denetleyebilir mi, ve bu denetim gerçek bir kalite kapısı olabilir mi?**

Ayırt edici nokta agent'ların konuşması değil, **birbirini reddedebilmesidir.** Denetleyici, uygulayıcının çıktısını gerekçeli olarak geri çevirir ve revizyon ister. Bu döngü sistemin ana mekanizmasıdır, opsiyonel bir ekstra değil.

Problemi somutlaştırmak için alan olarak **tarayıcıda oynanabilir basit oyunlar** seçildi. Gerekçe: oyun mantığı saf hesaplamadır (deterministik test edilebilir), çıktı gözle görülür (jüri ekranda oynayabilir), ve kapsamı ölçülebilir biçimde sınırlanabilir.

### 1.1 Neden bu problem zor

| Zorluk | Neden önemli |
|---|---|
| Denetleyici her şeyi onaylayabilir | O zaman sistem "üç agent sırayla konuştu"ya düşer; denetim mekanizması anlamsızlaşır |
| Denetleyici kendi kararını uydurabilir | Serbest metinde geçen "KABUL" kelimesi karar sayılırsa üretilen koddaki bir yorum satırı sistemi kandırır |
| Sonsuz revizyon döngüsü | Aynı sorunu çözemeyen iki agent birbirini sonsuza dek reddedebilir; token ve para yakar |
| Üretilen kod güvenilmez | Sistem AI'ın yazdığı kodu **gerçekten çalıştırır**; bu gerçek bir tehdit modeli demektir |
| LLM deterministik değil | Aynı girdi aynı çıktıyı vermez; test edilebilirlik ciddi bir tasarım problemi olur |

---

## 2. Paydaşlar

| Paydaş | Beklentisi | Bu belgede karşılığı |
|---|---|---|
| **Değerlendirici / eğitmen** | Sistemi kendi makinesinde sorunsuz ayağa kaldırmak, mekanizmayı ve sınırlarını görmek | US-01, US-07, US-10 |
| **Son kullanıcı** | Doğal dille oyun istemek, sonucu oynamak, kendi API anahtarını kullanmak | US-02, US-04, US-05, US-06 |
| **Sistem sahibi (geliştirici)** | Maliyetin ve döngünün kontrolden çıkmaması, üretilen kodun izole kalması | US-09, US-11 |

---

## 3. User story'ler

Her story `US-nn` ile numaralanır ve §4'teki kabul kriterlerine bağlanır.

### Kurulum ve erişilebilirlik

**US-01** — *Değerlendirici olarak*, sisteme yalnızca Docker kurulu bir makinede tek komutla erişmek istiyorum, *çünkü* değerlendirme sırasında bağımlılık kurulumuyla uğraşmak istemiyorum.
→ KK-11

**US-07** — *Değerlendirici olarak*, hiçbir API anahtarı girmeden sistemi uçtan uca çalışırken görmek istiyorum, *çünkü* kendi anahtarımı harcamadan mekanizmanın çalıştığını doğrulamak istiyorum.
→ KK-12

### Temel akış

**US-02** — *Kullanıcı olarak*, bir sohbet kutusuna doğal dille oyun istemek istiyorum, *çünkü* teknik bir şartname yazmak istemiyorum.
→ KK-01, KK-16

**US-03** — *Kullanıcı olarak*, agent'ların birbirini nasıl denetlediğini adım adım görmek istiyorum, *çünkü* sonucun nasıl oluştuğuna güvenmek istiyorum.
→ KK-07, KK-17

**US-04** — *Kullanıcı olarak*, üretilen oyunu aynı sayfada oynamak istiyorum, *çünkü* dosya indirip açmak akışı bozar.
→ KK-13

**US-05** — *Kullanıcı olarak*, birden çok oyun üretip aralarında geçiş yapmak istiyorum, *çünkü* ikinci istek birincisini silmemeli.
→ KK-14, KK-15

### Kontrol ve sınırlar

**US-08** — *Kullanıcı olarak*, sistemin yapamayacağı bir şeyi gerekçesiyle reddetmesini istiyorum, *çünkü* beş tur boyunca bozuk kod üretip pes etmesi zaman ve para kaybıdır.
→ KK-08, KK-09

**US-09** — *Sistem sahibi olarak*, tur/token/süre/maliyet tavanlarının sert olmasını istiyorum, *çünkü* kontrolsüz bir agent döngüsü faturayı öngörülemez yapar.
→ KK-02, KK-03, KK-18

**US-11** — *Sistem sahibi olarak*, üretilen kodun izole çalışmasını istiyorum, *çünkü* sistem AI'ın yazdığı kodu gerçekten çalıştırıyor.
→ KK-04, KK-19, KK-20, KK-21

### Güvenlik ve denetlenebilirlik

**US-06** — *Kullanıcı olarak*, her agent için ayrı API anahtarı girmek istiyorum, *çünkü* farklı rollerde farklı sağlayıcı kullanmak isteyebilirim.
→ KK-22

**US-10** — *Değerlendirici olarak*, transkripti dışa aktarmak ve hangi prompt sürümünün hangi çıktıyı ürettiğini görmek istiyorum, *çünkü* denetlenebilirlik iddiasının kanıtı budur.
→ KK-07

**US-12** — *Kullanıcı olarak*, sistemin kendi anahtarımı hiçbir yere sızdırmamasını istiyorum, *çünkü* ona üçüncü taraf kimlik bilgisi emanet ediyorum.
→ KK-23, KK-24

### Sonradan eklenen story'ler

Aşağıdakiler ilk analiz turunda yoktu; sistem kullanılmaya başlandıktan sonra kullanıcı tarafından istendi.

**US-13** — *Kullanıcı olarak*, her agent için sağlayıcının kataloğundan model seçmek istiyorum, *çünkü* varsayılan kurulum benim ihtiyacım için fazla maliyetli ve hangi modellere eriştiğimi sistem bilemez.
→ KK-25, KK-26, KK-27

**US-14** — *Kullanıcı olarak*, geçmiş koşuların transkriptlerini okumak istiyorum, *çünkü* nerede ne olduğunu sonradan görebilmem gerekiyor.
→ KK-28

**US-15** — *Kullanıcı olarak*, ok tuşlarıyla oynanan oyunları sayfa kaymadan oynamak istiyorum.
→ KK-29

---

## 4. Kabul kriterleri (Given / When / Then)

> Durum makinesini doğrudan sınayan KK-01 … KK-07 aynı zamanda `PROJECT.md` §4.3'te özetlenmiştir. Tam liste burasıdır.

### Ana döngü ve durum makinesi

**KK-01** — *Given* geçerli bir görev girildi, *When* planlayıcı planı üretti, *Then* sistem `UYGULANIYOR` durumuna geçer ve planda en az bir kabul kriteri bulunur.

**KK-02** — *Given* tur limiti 5, *When* denetleyici 5. turda hâlâ reddediyor, *Then* sistem durur, `LIMIT_ASILDI` durumuna geçer ve son red gerekçesini içeren başarısızlık raporu üretir.

**KK-03** — *Given* denetleyici aynı gerekçeyle iki kez üst üste reddetti, *When* üçüncü tur başlatılacak, *Then* sistem ilerleme olmadığını tespit eder ve turu **başlatmadan** durur.

**KK-04** — *Given* uygulayıcı workspace dışına yazmayı denedi, *When* yol koruması devreye girer, *Then* işlem reddedilir, `HATA` durumuna geçilir ve ihlal transkripte kaydedilir.

**KK-05** — *Given* denetleyici serbest metin döndürdü, *When* JSON ayrıştırma başarısız olur, *Then* sistem kararı KABUL saymaz; bir kez yeniden dener, tekrar başarısız olursa `HATA` durumuna geçer.

**KK-06** — *Given* tüm testler geçti, *When* denetleyici KABUL döndü, *Then* sır taraması çalıştırılır; anahtar/token bulunursa KABUL geçersiz sayılır ve red turu başlatılır.

**KK-07** — *Given* sistem bir son duruma ulaştı, *When* kullanıcı transkripti dışa aktarır, *Then* JSON ve Markdown çıktısı üretilir ve **prompt sürüm hash'lerini** içerir.

### Uygulanabilirlik kapısı

**KK-08** — *Given* kullanıcı uygulanabilirlik ölçütünü geçemeyen bir oyun istedi (ör. satranç), *When* planlayıcı değerlendirmeyi yaptı, *Then* sistem `KAPSAM_DISI` durumuna geçer, hangi ölçütün ihlal edildiğini içeren gerekçeli bir rapor üretir ve bunu `HATA`dan ayrı bir sonuç olarak kaydeder.

**KK-09** — *Given* planlayıcı `UYGUN` dedi ama 10'dan fazla özel durum veya harici varlık dosyası ihtiyacı bildirdi, *When* karar değerlendirilir, *Then* sistem kararı geçersiz sayar ve `UYGUN_DEGIL` olarak işler. *Planlayıcı kendi ölçümüyle çelişemez.*

**KK-10** — *Given* kullanıcı bilinen-iyi dört oyunun dışında ama ölçütü geçen bir oyun istedi (connect-4, othello, 2048), *When* planlayıcı değerlendirmeyi yaptı, *Then* sistem planı üretir; oyun adının listede olmaması tek başına ret sebebi değildir.

### Kurulum ve erişilebilirlik

**KK-11** — *Given* yalnızca Docker kurulu temiz bir makine, *When* depo klonlanıp `docker compose up` çalıştırılır, *Then* sistem `localhost:8000` üzerinden açılır ve host'a Python, Node veya başka bir bağımlılık kurulmaz.

**KK-12** — *Given* `.env` dosyası yok, *When* sistem başlatılır, *Then* sistem hata vermeden açılır, `replay` sağlayıcısına düşer ve **hangi modda olduğunu ve nedenini** arayüzde gösterir.

### Oyun kütüphanesi

**KK-13** — *Given* kabul edilmiş bir oyun var, *When* kullanıcı "oynat" der, *Then* oyun aynı sayfada iframe içinde açılır ve iframe'e `allow-same-origin` verilmez.

**KK-14** — *Given* daha önce bir oyun üretildi, *When* ikinci bir görev verilir, *Then* ikinci oyun **yeni bir dizine** yazılır ve birincisi silinmez.

**KK-15** — *Given* birden çok tamamlanmış oyun var, *When* kullanıcı listeyi açar, *Then* oyunlar en yeniden eskiye listelenir; yalnızca `KABUL_EDILDI` durumundaki ve `game.html` dosyası bulunanlar oynanabilir işaretlenir.

### Girdi ve döngü kontrolü

**KK-16** — *Given* görev metni karakter sınırını aşıyor veya boş, *When* girdi doğrulanır, *Then* görev başlatılmaz ve hata mesajı **görev metnini yankılamaz**.

**KK-17** — *Given* bir görev çalışıyor, *When* her tur tamamlanır, *Then* transkripte rol, tur, prompt sürümü, prompt hash'i, model, token sayıları ve maliyet yazılır.

**KK-18** — *Given* token, süre veya maliyet tavanı doldu, *When* tur başında limit kontrolü yapılır, *Then* sistem `LIMIT_ASILDI` durumuna geçer ve **hangi limitin** dolduğunu raporlar.

### Sandbox ve güvenlik

**KK-19** — *Given* üretilen kod ağ, dosya sistemi veya süreç modülü kullanıyor, *When* statik içe aktarma denetimi çalışır, *Then* kod **hiç çalıştırılmaz**, denetleyiciye kritik bulgu iletilir ve revizyon turu başlar.

**KK-20** — *Given* üretilen test sonsuz döngüye giriyor veya belleği doldurmaya çalışıyor, *When* sandbox çalıştırılır, *Then* süreç kaynak limiti veya duvar saatiyle sonlandırılır ve sistem yanıt vermeye devam eder.

**KK-21** — *Given* üretilen kod ortam değişkenlerini okumaya çalışıyor, *When* sandbox çalıştırılır, *Then* alt süreçte hiçbir API anahtarı bulunmaz.

**KK-22** — *Given* kullanıcı bir agent için API anahtarı girdi, *When* anahtar listesi görüntülenir, *Then* yalnızca maskeli parmak izi (`••••9f3a`), uzunluk ve sağlayıcı döner; anahtarın kendisi hiçbir yanıtta geçmez.

**KK-23** — *Given* sağlayıcıdan anahtarı içeren bir hata mesajı geldi, *When* mesaj transkripte yazılır, *Then* anahtar birebir eşleşmeyle silinir ve dışa aktarımda bulunmaz.

**KK-24** — *Given* kullanıcı API anahtarını görev kutusuna yapıştırdı, *When* girdi doğrulanır, *Then* görev **başlatılmaz**; anahtar transkripte veya LLM sağlayıcısına gitmez.

### Model seçimi ve geçmiş

**KK-25** — *Given* bir sağlayıcı için anahtar girilmiş, *When* kullanıcı model listesini açar, *Then* liste **sağlayıcının kendi kataloğundan canlı** gelir; sabit bir listeden değil. Anahtar yoksa katalog reddedilir ve neden söylenir.

**KK-26** — *Given* kullanıcı bir rol için sağlayıcı ve model seçip kaydetti, *When* rol yapılandırması çözümlenir, *Then* **hem sağlayıcı hem model** seçimden gelir; başka bir sağlayıcının anahtarı bulunsa bile seçim ezilmez.

**KK-27** — *Given* seçim kaydedildi, *When* bir görev tamamlanır **veya** konteyner yeniden başlatılır, *Then* seçim korunur ve arayüzde aynı değer görünür.

**KK-28** — *Given* daha önce tamamlanmış koşular var, *When* kullanıcı bir kaydın transkriptini açar, *Then* görev metni, son durum, uygulanan geçiş kuralı, token/maliyet toplamı, **prompt sürüm hash'leri** ve tüm agent mesajları görünür; JSON ve Markdown olarak indirilebilir.

**KK-29** — *Given* ok tuşlarıyla oynanan bir oyun açık, *When* kullanıcı tam ekrana geçer, *Then* oyun iframe sandbox'ını **koruyarak** tam ekran olur ve ok tuşları ana sayfayı kaydırmaz.

---

## 5. Kapsam

### 5.1 Kapsam içi

| Konu | Kapsam |
|---|---|
| Üretilebilir oyunlar | **İsim listesiyle değil ölçütle** belirlenir (§5.2). Bilinen-iyi örnekler: tic-tac-toe, snake, pong, breakout |
| Çıktı biçimi | Tek dosyalık `game.html` (canvas + JS) + ayrı `logic.js` mantık modülü |
| Test | `logic.js` üzerinde `node --test` ile çalışan `logic.test.js`, sıfır bağımlılık |
| Agent sayısı | 3 — planlayıcı, uygulayıcı, denetleyici |
| Arayüz | Web — canlı transkript, oyun iframe'i, oyun kütüphanesi, transkript dışa aktarımı |
| Sağlayıcılar | Anthropic, OpenAI, Ollama ve test için kayıt/oynatma sahte sağlayıcısı |
| Kalıcılık | Her görev kendi dizininde; oturum sonrası erişilebilir, oyunlar arası geçiş mümkün |

### 5.2 Uygulanabilirlik ölçütü

Sabit bir oyun listesi, "başa çıkabileceğimiz karmaşıklık" için **kötü bir vekil ölçüdür**: connect-4 listede olmadığı için reddedilirdi, oysa snake'ten kolaydır. Ölçütün kendisi yazılır, sonucu değil:

| # | Ölçüt | Geçemezse |
|---|---|---|
| U1 | Oyun durumu tek bir veri yapısında tutulabiliyor mu | Kapsam dışı |
| U2 | Özel durum / kural istisnası sayısı ≤ 10 mu | Kapsam dışı |
| U3 | Bitiş ve kazanma koşulu saf fonksiyonla test edilebiliyor mu | Kapsam dışı |
| U4 | Harici varlık **dosyası** (`.png`, `.mp3`, sprite atlası) gerekiyor mu | Gerekiyorsa kapsam dışı |
| U5 | Gerçek zamanlı animasyon gerekiyor mu | **Tek başına diskalifiye etmez** |

**U4 kodla üretilen varlığı kapsamaz.** Kısıtın kaynağı tek dosyalık teslimdir, sesin kendisi değil: canvas çizimleri ve Web Audio osilatörüyle üretilen tonlar saf koddur. Sınama sorusu: *"Bu oyun tek bir HTML dosyası olarak, yanında başka hiçbir dosya olmadan teslim edilebilir mi?"* Bu ayrım olmadan **flappy bird gibi kapsam içi olması gereken oyunlar yalnızca tıklama sesi yüzünden reddedilirdi.**

### 5.3 Kapsam dışı — gerekçeleriyle

| Konu | Neden dışarıda |
|---|---|
| **Satranç** | Adı yasaklı olduğu için değil, **U2'yi geçemediği için**: rok, en passant, şah/mat, terfi, pat ve geçerli hamle üretimi özel durum tavanını fazlasıyla aşar. Sistem bunu çalışma anında değerlendirir ve gerekçeli olarak reddeder. 3. gün **hata senaryosu demosu** budur |
| Çok oyunculu / ağ üzerinden oyun | Ağ katmanı sandbox politikasıyla çelişir; statik denetim ağ modüllerini reddeder |
| 3B grafik, ses varlıkları, harici görsel | Tek dosyalık teslim kısıtını bozar (U4); üretim süresi ve token maliyeti öngörülemez hale gelir |
| Kullanıcı hesabı, oturum yönetimi, çok kullanıcılı eşzamanlılık | 3 günlük süre kısıtı; tek kullanıcılı yerel çalıştırma varsayılmıştır (V3) |
| Agent'ların kendi promptlarını değiştirmesi | Promptlar sürümlü dosyalardır; çalışma anında değiştirilemez — denetlenebilirlik şartı |
| Üretilen oyunun görsel kalitesinin otomatik değerlendirilmesi | Denetleyici mantığı test eder, estetiği değil |
| Gömme tabanlı RAG | Uygulanabilirlik bir arama değil bir yargıdır; ayrıca 3 günde toplanacak 6–8 belge üzerinde vektör araması, belgeleri doğrudan bağlama koymaktan kötüdür. Yerine sürümlü **kural kartı** deposu planlandı |

---

## 6. Varsayımlar

| # | Varsayım | Doğrulanmazsa etkisi | Durum |
|---|---|---|---|
| V1 | Değerlendirici makinesinde yalnızca Docker kurulu | Tek ön koşuldur; Python, Node ve bağımlılıklar imajın içindedir | ✅ Doğrulandı (464 MB imaj, temiz derleme) |
| V2 | En az bir LLM sağlayıcısına erişim var veya Ollama lokal kurulu | Sahte sağlayıcı ile kayıtlı senaryolar yine de çalışır | ✅ Tasarımla karşılandı |
| V3 | Tek kullanıcı, tek eşzamanlı görev | Eşzamanlı görev desteği yok; ikinci görev sıraya alınmaz | ⬜ Faz 5'te uygulanacak |
| V4 | Üretilen oyun kodu güvenilmez kabul edilir | Tüm çalıştırma sandbox içinde | ✅ Faz 2'de uygulandı ve ölçüldü |
| V5 | Üretilen oyun mantığının ağ, dosya sistemi veya süreç erişimine meşru ihtiyacı yoktur | Statik izin listesinin meşruiyeti bu varsayıma dayanır | ✅ Kapsam içi oyunlar için geçerli |

---

## 7. Kısıtlar

| # | Kısıt | Kaynağı |
|---|---|---|
| K1 | Toplam geliştirme süresi 3 gün (14–16 Ağustos 2026) | Akademi takvimi |
| K2 | Teslimlerin tamamı zorunlu; eksik teslim projeyi değerlendirme dışı bırakır | Program sunumu |
| K3 | Demo 5 dakika: mutlu senaryo + en az bir hata senaryosu | Sunum |
| K4 | **Prompt'lar insan tarafından yazılır**; kod üretimi AI'a bırakılabilir | Eğitmen kuralı |
| K5 | Sistem eğitmenlerin kendi makinelerinde dockerize çalışmalıdır | Eğitmen kuralı |
| K6 | Docker içinde Docker yoktur; Docker soketi bağlanmaz | Proje sahibi kararı |
| K7 | Teslim zip dosyası; sürüm takibi private GitHub deposunda | Proje sahibi kararı |

---

## 8. Fonksiyonel olmayan gereksinimler

| # | Gereksinim | Ölçüt | Durum |
|---|---|---|---|
| FO-01 | İlk derleme süresi | < 3 dakika | ✅ ~1 dk |
| FO-02 | İmaj boyutu | < 500 MB | ✅ 438 MB |
| FO-03 | Otomatik test paketi süresi | < 60 sn | ✅ ~18 sn (379 test) |
| FO-04 | Hiçbir otomatik test gerçek API çağrısı yapmaz | Kod incelemesi | ✅ |
| FO-05 | Oyun başına maliyet | < $0.50 | ✅ **$0.179–0.221** (15.08 ölçümü) |
| FO-06 | Sandbox zaman aşımı | 30 sn | ✅ Ölçüldü |
| FO-07 | Sistem anahtarsız açılabilir | `.env` yokken çalışır | ✅ Doğrulandı |

---

## 9. Riskler

| # | Risk | Etki | Azaltıcı | Durum |
|---|---|---|---|---|
| R1 | LLM 5 tur içinde çalışan oyun üretemez | Çalışan ürün kalemi zedelenir | Kapsam ölçütü riskli oyunları baştan eler | ✅ **Gerçekleşmedi** — tic-tac-toe ve connect-4 **tek turda** kabul edildi (15.08) |
| R2 | Prompt ile şema birbirinden sapar | Sistem her turda şema hatası verir, sebep "LLM saçmalıyor" sanılır | `test_prompt_ornekleri.py` — prompt örnekleri şemaya karşı doğrulanır | ✅ Kapatıldı |
| R3 | Denetleyici her şeyi kabul eder | Sistemin ana mekanizması anlamsızlaşır | Yapısal JSON karar, test sonucuyla çelişme yasağı, `test_sonucu`nun orkestratörce ölçülmesi | ✅ Kapatıldı |
| R4 | Statik denetim gizlenmiş kodla atlatılır | Ağ erişimi mümkün olur | Bilinçli sınır (S2): atlatılsa dahi ayrıcalık düşürme, rlimit ve konteyner sınırı devrede | ⚠️ Kabul edildi |
| R5 | Arayüzde kimlik doğrulama yok | `localhost:8000`'e erişen anahtarı kullanabilir | Bilinçli sınır (S5): port `127.0.0.1`'e bağlı, anahtar bellekte, açık temizleme eylemi | ⚠️ Kabul edildi |
| R6 | Geç gelen gereksinim kapsamı bozar | Revizyon maliyeti | Üç açık soru 14.08'de kapatıldı; kalan gereksinim beklenmiyor | ✅ Kapatıldı |
| R7 | **Mantık doğru olduğu hâlde oyun kullanıcıya yanlış görünür** | Sistem "kabul edildi" der, kullanıcı bozuk bir oyun oynar | Sunum katmanı hiçbir kapıdan geçmiyor (bilinen sınır S6). Azaltıcı yön: anlamsal eşlemelerin `logic.js`'e taşınması (§10.1) | ⚠️ **Gerçekleşti** — 15.08 connect-4 renk eşlemesi. İnsan testi buldu, 352 otomatik test bulamadı |

---

## 10. İzlenebilirlik matrisi

Her kabul kriterinin bir teste karşılığı vardır. Boş kalan satırlar **henüz uygulanmamış fazlara** aittir ve açıkça işaretlenmiştir.

| KK | Story | Doğrulayan test | Durum |
|---|---|---|---|
| KK-01 | US-02 | `test_state_machine.py::test_g2_plan_uretildi` | ✅ |
| KK-02 | US-09 | `test_state_machine.py::test_g8_tur_tavani_dolunca_limit_asildi` | ✅ |
| KK-03 | US-09 | `test_state_machine.py::test_g11_ayni_gerekce_iki_kez_ust_uste_durdurur` | ✅ |
| KK-04 | US-11 | `test_state_machine.py::test_g5_yol_ihlali_kurtarilamaz` + `test_security.py` (T1, 8 test) | ✅ |
| KK-05 | US-03 | `test_state_machine.py::test_g9_ikinci_ayristirma_hatasi_kabul_sayilmaz` | ✅ |
| KK-06 | US-11 | `test_state_machine.py::test_g6s_sir_bulunursa_kabul_gecersizdir` | ✅ |
| KK-07 | US-10 | `test_transcript.py::test_json_disa_aktarimi_prompt_hashlerini_icerir` | ✅ |
| KK-08 | US-08 | `test_state_machine.py::test_g2k_uygulanabilir_bulunmadi_kapsam_disi` | ✅ |
| KK-09 | US-08 | `test_feasibility.py::test_ozel_durum_tavani_asilirsa_uygun_karari_gecersiz` | ✅ |
| KK-10 | US-02 | `test_feasibility.py::test_listede_olmayan_oyunlar_reddedilmez` | ✅ |
| KK-11 | US-01 | Elle doğrulama (14.08): temiz derleme + `docker compose up` | ✅ |
| KK-12 | US-07 | `test_key_vault.py` + canlı sağlık ucu doğrulaması | ✅ |
| KK-13 | US-04 | `test_library.py::test_oynanabilir_oyun_dosyasi_sunulur` + tarayıcı doğrulaması | ✅ |
| KK-14 | US-05 | `test_library.py::test_ayni_saniyede_ikinci_gorev_cakismaz` | ✅ |
| KK-15 | US-05 | `test_library.py::test_oyunlar_en_yeniden_eskiye_siralanir` | ✅ |
| KK-16 | US-02 | `test_security.py::test_hata_mesaji_gorev_metnini_yankilamaz` | ✅ |
| KK-17 | US-03 | `test_transcript.py::test_agent_mesaji_koken_bilgisi_olmadan_kaydedilemez` | ✅ |
| KK-18 | US-09 | `test_limits.py` (13 test) | ✅ |
| KK-19 | US-11 | `test_sandbox.py::test_yasak_modul_kullanan_kod_hic_calistirilmaz` | ✅ |
| KK-20 | US-11 | `test_sandbox.py::test_duvar_saati_asimi_sigkill_ile_biter` | ✅ |
| KK-21 | US-11 | `test_sandbox.py::test_api_anahtari_alt_surece_gecmez` | ✅ |
| KK-22 | US-06 | `test_key_vault.py::test_parmak_izi_anahtarin_kendisini_icermez` | ✅ |
| KK-23 | US-12 | `test_key_vault.py::test_saglayici_hatasi_transkripte_anahtarla_girmez` | ✅ |
| KK-24 | US-12 | `test_security.py::test_gorev_metnindeki_anahtar_gorevi_durdurur` | ✅ |
| KK-25 | US-13 | `test_web_api.py::test_katalog_anahtarsiz_reddedilir` | ✅ |
| KK-26 | US-13 | `test_selection.py::test_secim_saglayiciyi_da_belirler` | ✅ |
| KK-27 | US-13 | `test_selection.py::test_secim_diske_yazilir_ve_geri_okunur` | ✅ |
| KK-28 | US-14 | `test_library.py` (dosya sunumu) + tarayıcı doğrulaması | ✅ |
| KK-29 | US-15 | Tarayıcı doğrulaması (otomatik test kapsamı dışı) | ✅ |

**Test dağılımı (15.08.2026, 379 test, ~18 sn):**

| Dosya | Test | Kapsadığı |
|---|---|---|
| `test_security.py` | 62 | T1, T2b, T3, T5 |
| `test_state_machine.py` | 47 | 16 geçiş, tüm koruma koşulları |
| `test_provider.py` | 32 | Sağlayıcı sözleşmesi, maliyet, kayıt/oynatma |
| `test_library.py` | 28 | Kütüphane, yol koruması |
| `test_reviewer_parsing.py` | 25 | T4 — sahte KABUL |
| `test_selection.py` | 24 | Model seçimi, sağlayıcı-farkında varsayılanlar |
| `test_feasibility.py` | 23 | Uygulanabilirlik ölçütü |
| `test_key_vault.py` | 22 | T7, T8 |
| `test_mcp.py` | 22 | MCP sunucusu + istemcisi |
| `test_web_api.py` | 22 | HTTP uçları, anahtar sızıntısı |
| `test_sandbox.py` | 18 | T2, T4b — gerçek süreç |
| `test_transcript.py` | 16 | Mesaj zarfı, dışa aktarım |
| `test_loop.py` | 15 | Uçtan uca, red/revizyon döngüsü |
| `test_limits.py` | 13 | T6 |
| `test_prompt_ornekleri.py` | 10 | Prompt–şema sapması |

**Hiçbir otomatik test gerçek API çağrısı yapmaz.**

---

## 11. Açık maddeler

| # | Madde | Kapanacağı yer |
|---|---|---|
| A1 | Denetleyici `KABUL` derken `kritik` bulgu bildirirse ne olmalı? Spesifikasyonda kural yok; mevcut davranış testle kayda geçirildi, karar insana bırakıldı | Faz 4 öncesi |
| A2 | ~~Oyun başına gerçek token ve maliyet~~ | ✅ Ölçüldü: $0.179–0.221, ~13.700 token |
| A3 | ~~"Satranç LLM için çok zor" iddiası~~ | ✅ Kanıtlandı: sistem 24 özel durum sayarak reddetti |
| A4 | Kural kartı MCP aracı | Kapsam dışı bırakıldı — filesystem MCP sunucusu şartı zaten karşılıyor |
| A6 | **Red/revizyon döngüsü gerçek koşuda henüz gözlenmedi.** Dört koşunun dördü de tek turda kabul aldı. Mekanizma `test_loop.py` ile uçtan uca sınandı ama canlı örneği kayıtlı değil | Demo öncesi bir koşu denenecek: planlayıcı güçlü + uygulayıcı zayıf model, kural karmaşıklığı yüksek oyun (othello). Çıkmazsa **öyle raporlanacak** — red garantilemek için prompt'a müdahale edilmeyecek |
| A5 | **Sunum katmanı boşluğu (S6/R7) prompt'larla kapatılsın mı?** | Kural K4 gereği prompt değişikliği insana ait. İki aday: (1) planlayıcı prompt'una "işaret→oyuncu/renk eşlemesi `logic.js`'te dışa aktarılmalı ve test edilmeli" kuralı; (2) denetleyici prompt'una "sunumun mantıkla **anlamsal** tutarlılığı denetlenir; estetik denetlenmez" ayrımı. Karar insanda |

---

## 12. Değişiklik kaydı

| Sürüm | Tarih | Değişiklik |
|---|---|---|
| 1.1 | 15.08.2026 | Sonradan eklenen üç story (US-13 model seçimi, US-14 transkript geçmişi, US-15 tam ekran oynatıcı) ve beş kabul kriteri (KK-25…29). R7 (sunum katmanı) gerçekleşmiş risk olarak işaretlendi; R1 gerçekleşmedi olarak kapandı. FO ölçümleri gerçek değerlerle güncellendi. İzlenebilirlik matrisi 29 satıra, test dağılımı 15 dosya / 379 teste çıktı. A6 açık maddesi eklendi: **red/revizyon döngüsü gerçek koşuda henüz gözlenmedi** |
| 1.0 | 14.08.2026 | İlk sürüm — 12 user story, 24 kabul kriteri, uygulanabilirlik ölçütü, varsayım/kısıt/risk tabloları, izlenebilirlik matrisi |
