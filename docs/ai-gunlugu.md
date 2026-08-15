# AI Çalışma Günlüğü

**Proje:** Agent-to-Agent Oyun Üretim Sistemi — GTech Yaz Akademisi Bitirme Projesi
**Yürüten:** Ümit İsmen (analist + developer)
**Kullanılan AI aracı:** Claude Code (CLI, VS Code eklentisi) — model: Claude Opus 5
**Günlük başlangıcı:** 14 Ağustos 2026

---

## Bu günlük neden var, nasıl tutuluyor

Değerlendirme kriterlerinin önemli bir bölümü "AI kullanım olgunluğu (context, prompt, denetim)" kalemine ayrılmış durumda. Bu kalem geriye dönük doldurulamaz: hangi kararın AI tarafından önerildiği, hangisinin insan tarafından verildiği veya düzeltildiği, ancak süreç anında kaydedilirse doğrulanabilir kalır.

Her kayıt dört alan içerir:

| Alan | İçerik |
|---|---|
| **Prompt** | İnsanın verdiği girdi, birebir |
| **AI çıktısı** | Modelin ürettiği cevabın özeti |
| **Karar sahibi** | Kararı kimin verdiği — AI önerisi mi, insan tercihi mi |
| **İnsan müdahalesi** | Neyin reddedildiği, düzeltildiği veya yeniden çerçevelendiği |

Bu dosya proje boyunca büyütülecektir. Aşağıdaki kayıtlar, henüz tek satır kod yazılmadan önceki **analiz ve karar aşamasını** kapsar.

---

## Oturum 1 — 14 Ağustos 2026: Kapsam analizi ve mimari kararlar

### Kayıt 1.1 — Sunumun analizi

**Prompt:**

> Proje dosyası içerisinde bir powerpoint sunumu mevcut. İçerisinde göreceğin üzere tüm proje kapsamı ve gereklilikler mevcut. Bu proje GTech Yaz akademisi bitirme projesi olarak geçiyor ve işe alım sürecim için önemli. Önce sunumu incelemeni ve bana bulgularını paylaşmanı istiyorum. Daha sonrasında seninle birlikte karar aşamalarına geçeceğiz.

**AI çıktısı — özet:**

AI, `.pptx` dosyasını açıp (OOXML arşivi olarak çözüp slayt XML'lerinden metni çıkararak) sunumun tamamını okudu ve şu bulguları raporladı:

1. **Puanlama dağılımının asıl mesajı**: değerlendirme ağırlıkları programın kendi materyalinde tanımlı. AI bunun altını çizdi: *"puanın dörtte üçü üründe değil"* — dolayısıyla iddialı bir ürün seçip dokümana zaman bırakmamak bu rubrikte en pahalı hata.
2. **Zorunlu teslimler** listelendi ve eksik teslimin projeyi değerlendirme dışı bıraktığı vurgulandı.
3. **Proje seçenekleri** kriterlere uyum açısından karşılaştırıldı; her biri için güçlü ve riskli taraf tablolandı.
4. **Bir çıkarım**: sunumdaki test senaryosu örnekleri doğrudan e-ticaret/ödeme akışı kenar durumları. AI bundan, rubriğin bu senaryolar düşünülerek yazılmış olabileceği sonucunu çıkardı ve Proje 3/5'i "rubriğe en hazır eşleşen" seçenekler olarak işaretledi.
5. **Sunumda cevabı olmayan noktalar** listelendi: süre, teknoloji serbestliği, bireysel/ekip, teslim formatı, demo formatı.

**Karar sahibi:** AI (analiz), insan (yönlendirme).

**İnsan müdahalesi:** Yok — bu adım bilgi toplama amaçlıydı. Ancak AI'ın "Proje 3/5 rubriğe en uygun" çıkarımı bir sonraki adımda insan tarafından **kabul edilmedi**; bkz. Kayıt 1.2.

---

### Kayıt 1.2 — Proje ve rol seçimi

**Prompt:**

> Agent - To - Agent benim en kendime güvendiğim nokta. Agentic AI hakkında bir Udemy kursu almış olmam sebebiyle mimarisine de hakimim. Aynı zamanda hem analiz hem de developer olarak konumlanacağım.

**AI çıktısı — özet:**

AI seçimi onaylamadan önce riski açıkça söyledi: Proje 1, AI olgunluğu kalemini doğal olarak kazandırırken **güvenlik/test ve çalışan ürün kalemlerinde en riskli seçenek**. Ardından bu riski kapatacak üç mühendislik önerisi getirdi:

1. **Somut çıktı zorunluluğu** — agent'lar sadece konuşup metin üretirse "ürün nerede?" sorusu doğar; sistemin sonunda dosyaya yazılan, açılıp bakılabilen bir teslim olmalı.
2. **Güvenlik yüzeyinin bilinçli inşası** — sandbox kaçışı, prompt injection, sır sızıntısı, maliyet/DoS tavanı. Sunumun zaten istediği "sonsuz döngü koruması, tur ve token limiti" şartını *test edilebilir* hale getirmek.
3. **Record/replay sahte LLM sağlayıcısı** — LLM non-determinizmi kabul testlerini imkânsız kılıyor; LLM çağrısını arayüz arkasına alıp kaydet-tekrar oynat sahte sağlayıcı yazmak hem test kalemini hem demo güvenilirliğini kurtarıyor.

AI ayrıca bir "bedava kazanç" tespit etti: agent turlarının durum makinesi (`planlanıyor → uygulanıyor → denetleniyor → reddedildi → kabul edildi → limit_aşıldı`), analist B bloğunun "durum makinesi tablosu" gereksinimini doğrudan karşılıyor; kabul kriterleri de doğal Given/When/Then formuna oturuyor.

Sonrasında üç soru sordu: **görev alanı**, **dil + orkestrasyon yaklaşımı**, **arayüz**.

**Karar sahibi:** İnsan (proje ve rol seçimi), AI (risk analizi ve telafi önerileri).

**İnsan müdahalesi:** AI'ın Kayıt 1.1'de işaret ettiği "rubriğe en hazır" seçenekler (Proje 3 e-ticaret / Proje 5 sanal POS) **reddedildi**. İnsan, mevcut yetkinliğini (agentic AI mimarisi, Udemy kursu) rubrik uyumundan üstün tuttu. Bu bilinçli bir takas: rubrik uyumu kaybedildi, uygulama hızı ve derinliği kazanıldı — ve AI'ın önerdiği üç telafi mekanizması bu takasın maliyetini kapatmak için kabul edildi.

**Seçilen cevaplar (üçü de AI'ın önerdiği seçenek):**

| Soru | Seçim |
|---|---|
| Görev alanı | Kod üretim + inceleme hattı |
| Dil / orkestrasyon | Python + kendi ince orkestrasyon katmanı (framework'süz) |
| Arayüz | Web arayüzü — canlı transkript izleyici |

AI'ın framework'süz orkestrasyon gerekçesi kayda değer: *"rubrik tam da bu kontrol mekanizmalarını (döngü koruması, token limiti, durdurma koşulu) puanlıyor; framework kullanılırsa bunlar kütüphanenin içinde kalır ve senin ne yaptığın görünmez."*

---

### Kayıt 1.3 — Kısıtlar, proje fikrinin yeniden çerçevelenmesi ve maliyet

**Prompt:**

> a) Bence docker en mantıklısı
> b) MCP tercihi tam olarak ne gibi bir görev alacak burada hala çözmüş değilim.
> c) hedef dil python bence de
> d) 3 Gün süremiz var
>
> Benim kafamda şöyle bir proje fikri var aslında. Basit oyunları prompt vererek yazdırabileceğimiz bir proje nasıl olur sence? tic tac toe, pong, satranç vb gibi oyunları chatbox'a yazarak yazdırsak mesela çok mu maliyetli olur? Aklımda kullanılacak LLM olarak ya Claude API,

**Aynı tur içinde gelen ek prompt:**

> OpenAI ya da OLLAMA var hatta bu üçünü de kullanabiliriz duruma göre

**AI çıktısı — özet:**

1. **Maliyet sorusu — hafızadan cevaplanmadı.** AI, LLM fiyatlandırması sorulduğunda güncel fiyat referansını yükleyerek cevapladı; eğitim verisinden hatırlanan fiyat kullanılmadı. Hesap: bir tam koşu (3 agent turu + ~2 revizyon) kabaca 30k girdi + 12k çıktı token. Oyun başına Opus 5 ile ~$0.45, Sonnet 5 ile ~$0.18, Haiku 4.5 ile ~$0.09, Ollama ile $0. Prompt caching ve record/replay sahte sağlayıcı hesaba katılınca toplam geliştirme maliyeti **$10–25 bandı**. Ek tespit: Sonnet 5'in tanıtım fiyatı 31 Ağustos 2026'ya kadar geçerli, yani proje penceresinin tamamını kapsıyor.

2. **Çok sağlayıcılı yapı rubrik varlığına dönüştürüldü.** AI, üç sağlayıcının zaten planlanan `llm/` arayüzünün doğal sonucu olduğunu, ekstra iş gerektirmediğini; ve sunumun *"kullanılan AI araç ve model kararları"* şartını karşılamanın en güçlü yolu olduğunu belirtti. Rol/model tablosu önerdi (Planlayıcı ve Denetleyici: Opus 5, Uygulayıcı: Sonnet 5, offline yedek: Ollama) ve Ollama'nın savunma değerini vurguladı: demo sırasında API çökerse veya kota biterse sistem çalışmaya devam eder.

3. **Oyun fikri desteklendi, bir uyarıyla.** AI, fikrin kendi "agent'lar ekrana metin basarsa ürün nerede?" endişesini tam olarak çözdüğünü belirtti. Ancak **satrancı tuzak olarak işaretledi**: rok, en passant, mat tespiti, geçerli hamle üretimi — LLM'in birkaç turda hatasız satranç yazma ihtimali düşük ve demo günü kırılacak yer tam orası. Öneri: satrancı denemek yerine **gerekçeli kapsam dışı maddesine** dönüştürmek. Gerekçe: analiz dokümanı zaten "kapsam dışı ile varsayım ve kısıt tablosu" istiyor; kendi sisteminin sınırını bilmek, sınırı aşmaya çalışıp başarısız olmaktan daha çok puan getirir.

4. **Test edilebilirlik için mimari ayrım önerildi:** oyunun **saf mantığı** (kazanma kontrolü, geçerli hamle, durum) ile **görsel katmanı** ayrı dosyalara. Denetleyici testleri sadece mantığa koşar → deterministik test + oynanabilir oyun, ikisi birden.

5. **Bir çelişki yüzeye çıkarıldı.** İnsanın (c) şıkkında verdiği "hedef dil Python" cevabı, oyun fikriyle birlikte sorun yaratıyordu: Python + oyun = pygame, bu da oyunun tarayıcıda açılamaması demek. AI bunu gizlemek yerine açık bir karar noktası olarak sundu ve HTML+JS alternatifini önerdi — çünkü oyun web arayüzünde transkriptin yanında iframe'de açılabilir, ve rubrikte birebir yazan *"hatasız kurulabilen ürün"* şartı için kurulum sıfıra iner.

6. **MCP'nin rolü netleştirildi** (insanın (b) şıkkındaki sorusuna cevap): Uygulayıcı agent'ın workspace dosya işlemleri (`read_file` / `write_file`), doğrudan Python çağrısı yerine filesystem MCP sunucusu üzerinden yürütülür. Böylece hem sunumun "en az bir MCP / dış araç çağrısı" şartı özgün biçimde karşılanır, hem izin listesi ve kök dizin politikası MCP katmanında gösterilebilir hale gelir.

**Karar sahibi ve müdahale — bu kayıt iki yönlü:**

- **İnsan → AI yönünde en önemli katkı burada.** AI, Kayıt 1.2'de görev alanını genel bir "kod üretim + inceleme hattı" olarak tanımlamıştı. **Oyun fikri insana aittir** ve alanı somutlaştırarak projeyi belirgin biçimde güçlendirmiştir: soyut bir kod üretim hattı yerine, jürinin ekranda oynayabileceği bir çıktı. AI bu fikri üretmedi, değerlendirdi ve üzerine inşa etti.
- **Çok sağlayıcı kararı da insana aittir.** AI tek sağlayıcı (Claude) varsayımıyla ilerliyordu; OpenAI ve Ollama'yı gündeme getiren insandır. AI bunu sonradan rubrik avantajına çevirmiştir.
- **AI → insan yönünde iki düzeltme:** (i) satrancın kapsam dışına alınması, (ii) hedef dilin Python'dan HTML+JS'e revize edilmesi. İkincisi insanın kendi verdiği bir cevabın geri alınması anlamına geliyordu; AI bunu sessizce uygulamak yerine gerekçeleriyle karar noktası olarak sundu.
- **AI'ın kendi kısıtı:** Kayıt 1.2'deki mimari öneriler (framework'süz orkestrasyon, web arayüzü) **süre bilgisi olmadan** verilmişti. 3 gün kısıtı ancak bu kayıtta öğrenildi ve kapsam buna göre budandı. Öneri sırasının tersine dönmüş olması bir süreç zaafıdır; ileriki oturumlarda kısıtlar karar öncesi sorulacaktır.

**Seçilen cevap:** Tek dosyalık HTML+JS oyun (AI'ın önerdiği seçenek).

---

### Kayıt 1.4 — Planlama ve günlüğün başlatılması

**Prompt:**

> AI çalışma günlüğünü başlat buraya kadarki kısmı yaz benim promptlarımı al ve kendi döndürdüğün cevapları özetleyerek betimle.

**AI çıktısı — özet:** Bu dosyanın kendisi. Önceki turda AI, 3 günlük planı çıkarmış ve *"bugün, şu andan itibaren yapman gereken tek şey AI çalışma günlüğünü başlatmak"* önerisinde bulunmuştu; insan bunu doğrudan uygulamaya aldı.

**Karar sahibi:** AI (öneri), insan (uygulama kararı ve zamanlama).

---

## Karar kütüğü

Bu tablo, projenin tüm bağlayıcı kararlarını ve sahiplerini özetler.

| # | Karar | Sahibi | Not |
|---|---|---|---|
| 1 | Proje 1 (Agent-to-Agent) seçimi | **İnsan** | AI'ın rubrik uyumu önerisine rağmen; mevcut yetkinlik üstün tutuldu |
| 2 | Hem analist hem developer konumlanma | **İnsan** | E bloğu (context paketi) döngüsünü kapatmayı mümkün kılıyor |
| 3 | Görev alanı: kod üretim + inceleme hattı | AI önerisi → insan onayı | |
| 4 | **Alanın oyun üretimine özelleştirilmesi** | **İnsan** | Projenin demo gücünü belirleyen karar |
| 5 | Framework'süz kendi orkestrasyon katmanı | AI önerisi → insan onayı | Rubrik kontrol mekanizmalarını puanlıyor |
| 6 | Web arayüzü + canlı transkript | AI önerisi → insan onayı | |
| 7 | Docker ile sandbox izolasyonu | **İnsan** | AI subprocess+timeout'u "3 günde daha düşük risk" diye önermişti; insan Docker'ı tercih etti |
| 8 | Hedef dil: HTML+JS (Python'dan revize) | AI düzeltmesi → insan onayı | iframe demosu ve sıfır kurulum gerekçesiyle |
| 9 | Satranç kapsam dışı | AI önerisi → insan onayı | Gerekçeli kısıt olarak belgelenecek |
| 10 | Üç sağlayıcı (Claude / OpenAI / Ollama) | **İnsan** | AI bunu rubrik avantajına çevirdi |
| 11 | Record/replay sahte LLM sağlayıcısı | AI önerisi → insan onayı | test kaleminin anahtarı |
| 12 | MCP rolü: workspace dosya işlemleri | AI önerisi → insan onayı | İnsanın açık sorusuna cevaben |
| 13 | 3 günlük süre kısıtı | **İnsan** (dış kısıt) | Tüm kapsamı belirleyen değişken |

**Dağılım:** 13 bağlayıcı karardan **5'i doğrudan insan tercihi** (2 tanesi AI önerisinin reddi/değiştirilmesi), 8'i AI önerisinin insan onayından geçmesi. AI'ın 2 düzeltmesi (satranç, hedef dil) insan tarafından kabul edildi.

---

## Denetim notları — AI çıktısının nerede sorgulanması gerekti

Rubrikteki "denetim raporu" gereksinimi için, bu aşamada AI çıktısının güvenilirlik değerlendirmesi:

| Konu | Durum | Nasıl doğrulandı / doğrulanacak |
|---|---|---|
| Sunum içeriğinin çıkarımı | Güvenilir | Metin doğrudan `.pptx` XML'inden çıkarıldı, özetlenmedi; slaytların tamamı okundu |
| Puanlama yüzdeleri | Doğrulandı | Ağırlıkların toplamı %100 olarak kontrol edildi |
| "Rubrik e-ticaret düşünülerek yazılmış" çıkarımı | **Yorum, kanıt değil** | Sunumdaki test senaryosu örneklerine dayanan bir çıkarım; eğitim koordinasyonuna doğrulatılmadı. Karar üzerinde etkisi olmadı (öneri zaten reddedildi) |
| LLM fiyatlandırması | Güvenilir | Hafızadan değil, güncel fiyat referansından alındı |
| Token tahminleri (30k girdi / 12k çıktı) | ✅ **Ölçüldü — tahmin 4 kat yüksekti** | Gerçek: tic-tac-toe **7.377 girdi / 6.304 çıktı**, connect-4 benzer. Tahmin muhafazakârdı; prompt önbelleği de payı düşürdü (planlayıcının ücretli girdisi 74 token'a indi) |
| Oyun başına maliyet ($0.18–0.45 tahmini) | ✅ **Ölçüldü — tahmin doğru bandın üstünde** | tic-tac-toe **$0.221**, connect-4 **$0.179**, satranç reddi **$0.012**. Tahmin bandının alt ucu tuttu |
| "Satranç LLM için çok zor" iddiası | ✅ **Kanıta dönüştü** (15.08) | Sistem satrancı `KAPSAM_DISI` ile reddetti ve **24 özel durum** sayarak gerekçelendirdi: altı taş türü için hamle üretimi, rok (kısa/uzun, hak kaybı, geçilen kare tehdidi), en passant, terfi, bağlı taş kısıtı, şah/mat, pat. İddia artık bir tahmin değil, sistemin ürettiği ölçüm |
| Uygulanabilirlik ölçütünün listeden üstün olduğu | ✅ **Kanıtlandı** (15.08) | **connect-4** — eski dört oyunluk listede olmayan bir oyun — tek turda üretildi, 9 test geçti, oynanabilir. Ölçüt hem açtı hem kapattı: connect-4 geçti, satranç geçemedi |
| `node --test`'in bağımlılıksız çalıştığı | ✅ **Doğrulandı** (14.08, Faz 0) | İmajda `runner` kullanıcısı olarak 2 test koşuldu, ikisi de geçti. `npm` imajda **yok** — bağımlılıksızlık iddiası artık imaj düzeyinde zorlanıyor, sadece beyan değil |
| Statik içe aktarma denetiminin yeterliliği | **Desen tabanlı — teorik olarak atlatılabilir** | Dize birleştirmeyle modül adı üreten gizlenmiş kod denetimi aşabilir. Negatif testlerle sınanacak; atlatılsa bile ayrıcalık düşürme, rlimit ve konteyner sınırı devrede kalır (tek katman değil, son katman delinir) |
| rlimit'lerin Docker Desktop altında uygulandığı | ⚠️ **Ölçüldü — kısmen yanlış çıktı** | `RLIMIT_CPU`, `RLIMIT_FSIZE`, `RLIMIT_NPROC` ve ayrıcalık düşürme doğrulandı. Ancak **`RLIMIT_AS` seçimi hatalıydı**: 512 MB'de meşru kod bile çöküyor. `RLIMIT_DATA`ya çevrildi. Ölçüm: `tests/manual/rlimit_olcumu.py`, ayrıntı Kayıt 1.8 |
| `docker compose up` eğitmen makinesinde çalışır | ✅ **Doğrulandı** (14.08, Faz 0) | Temiz derleme 464 MB imaj üretti, `.env` yokken açıldı, sağlık ucu yeşil |
| Oyunun iframe'de CSP altında açıldığı | ✅ **Doğrulandı** (14.08, insan tarafından) | Tarayıcıda açıldı, oyun `kazanan: X` çıktısını verdi. `sandbox="allow-scripts"` opak kaynağına rağmen `logic.js` yüklendi — CSP'ye sunucu kaynağının açıkça yazılması işe yaradı. Doğrulamayı AI değil **insan** yaptı: tarayıcı davranışı süreç içinden ölçülemiyordu |

**Açık risk:** Tabloda "tahmin" ve "test edilmedi" işaretli satırlar henüz doğrulanmamış AI çıktısıdır. Faz 0 üç satırı kapattı ve birinin **yanlış olduğunu** ortaya çıkardı; Faz 4'ün ilk gerçek koşuları dört satırı daha kapattı. **Kalan tek açık madde: statik denetimin gizlenmiş kodla atlatılabilirliği (S2)** — bu bilinçli bir sınırdır ve kapatılmayacaktır.

---

### Kayıt 1.5 — Çalışma kuralının netleşmesi ve `PROJECT.md` v1.0

**Prompt:**

> Eğitmenlerimiz promplarımız haricinde her şeyi AI'a yaptırabileceğimizi de söyledi. O konuda kendini kısıtlamana gerek yok. Artık PROJECT.md dosyasına başlayabiliriz.

**AI çıktısı — özet:**

AI, `PROJECT.md` v1.0'ı üretti. Dosyayı bilinçli olarak **iki işlevli** tasarladı: hem analist E bloğunun teslimi (context paketi), hem de sonraki iki gün kod üretilirken okunacak operasyonel referans. İçerik: ürün tanımı, kapsam/kapsam dışı (gerekçeli), varsayım ve kısıt tabloları, katman mimarisi ve tek yönlü bağımlılık kuralı, dizin yapısı, **7 durumlu 13 geçişli durum makinesi tablosu**, 7 Given/When/Then kabul kriteri, kontrol limitleri, 7 tehditlik güvenlik politikası, **mesaj şeması + alan sözlüğü**, sağlayıcı politikası, prompt yönetim kuralları, test stratejisi, kodlama kuralları, tamamlanma tanımı.

İki teslim burada bedavaya çıktı: durum makinesi tablosu ve alan sözlüğü, **analist B bloğunun** iki zorunlu maddesini doğrudan karşılıyor.

**Karar sahibi:** Dış kural (eğitim koordinasyonu), insan tarafından iletildi.

**Çalışma biçimine etkisi:** Bu kural sınırı netleştirdi — **promptlar (`prompts/*.md`) insan tarafından yazılır, kalan her şey AI'a bırakılabilir.** Kural `PROJECT.md` §2.4'e K4 kısıtı olarak, §9'a da prompt yönetim kuralı olarak işlendi. Bu ayrım günlüğün geri kalanı için de anlamlı: prompt dosyalarındaki her değişiklik insan kararıdır ve öyle kaydedilecektir.

---

### Kayıt 1.6 — Geç gelen gereksinim: dockerize çalıştırma

**Prompt** *(aynı tur içinde, `PROJECT.md` v1.0 yazıldıktan sonra geldi)*:

> Aynı zamanda eğitmenlerin lokallerinde dockerize etmemiz de isteniyor.

**AI çıktısı — özet:**

1. **Teknik çelişki hemen yüzeye çıkarıldı.** Sandbox için Docker kullanma kararı zaten alınmıştı; yeni şartla birlikte uygulamanın kendisi de konteynerde çalışacak. Yani **konteyner içindeki uygulama konteyner başlatacak.** AI bunu sessizce çözmek yerine (örneğin Docker soketini gerekçesiz bağlayarak) açık bir tasarım problemi olarak sundu.

2. **İki kademeli sandbox modu önerildi:**
   - `container` *(varsayılan)*: host Docker soketi app konteynerine bağlanır, app **kardeş** sandbox konteynerleri başlatır. Tam izolasyon.
   - `inprocess` *(yedek)*: soket erişilemezse `node --test` app konteyneri içinde ayrıcalıksız kullanıcı olarak, zaman aşımı ve yol kısıtıyla çalışır. Kısmi izolasyon, ama sistem çökmez.

   Yedek modun gerekçesi doğrudan demo riski: eğitmenin makinesinde soket bağlama çalışmazsa sistem tamamen durmak yerine düşük izolasyonla devam eder ve bu durumu arayüzde **görünür biçimde** belirtir.

3. **Anahtarsız çalışabilirlik zorunlu kılındı.** `.env` boşken sistem `replay` sağlayıcısıyla başlar; eğitmen hiçbir API anahtarı girmeden `docker compose up` yapıp sistemi uçtan uca çalışırken görebilir. AI bunun "hatasız kurulabilen ürün" kriterinin en güçlü kanıtı olduğunu belirtti.

4. **Güvenlik takası dürüstçe belgelendi.** Docker soketini bağlamak, app konteynerine host üzerinde root eşdeğeri yetki verir — yani uygulama, izole ettiği koddan daha ayrıcalıklı hale gelir. AI bunu gizlemek yerine `PROJECT.md` §6'ya **S1 numaralı bilinen sınır** olarak yazdı; sonucu, neden kabul edildiği ve azaltıcı faktörü (üretilen kod hiçbir zaman app konteynerinde çalışmaz; soket erişimi ile üretilen kod arasında sandbox sınırı vardır) birlikte kaydedildi. Yedek modun zayıf izolasyonu da S2 olarak eklendi.

5. **Geçmiş bir kararın geriye dönük doğrulandığı tespit edildi.** Kayıt 1.3'te hedef dil Python'dan HTML+JS'e çevrilmişti. Yeni şartla birlikte bu karar zorunlu hale geldi: pygame seçilseydi, eğitmenin konteynerden pencere görüntüleyebilmesi için X11/VNC forwarding kurması gerekecekti. HTML oyun ise konteynerdeki web sunucusundan tarayıcıya doğrudan geliyor.

6. `PROJECT.md` **v1.1**'e yükseltildi: K5 kısıtı, §3.3 dağıtım mimarisi bölümü, V1 varsayımının sadeleştirilmesi (artık tek ön koşul Docker), §6'ya S1–S4 bilinen sınırlar tablosu, §12 tamamlanma ölçütünün sıkılaştırılması.

**Karar sahibi:** Dış gereksinim (eğitim koordinasyonu) → AI tasarım çözümü → insan onayı.

**Süreç notu — bu kayıt bir zaafa işaret ediyor.** Gereksinim, `PROJECT.md` v1.0 tamamlandıktan **sonra** geldi ve aynı gün içinde v1.1 revizyonunu gerektirdi. Kayıt 1.3'te AI'ın kendi zaafı olarak not edilen durumun (kısıtların karar sonrası öğrenilmesi) bir benzeri, bu kez gereksinim tarafında tekrarlandı. Çıkarılan ders: **eğitim koordinasyonuna sorulacak açık soruların listesi (sunumun cevaplamadığı noktalar) proje başında sorulmalıydı.** Kalan açık sorular — teslim formatı (repo yapısı), demo canlı mı kayıt mı, bireysel/ekip — bir sonraki fırsatta toplu olarak sorulacaktır; aksi halde benzer geç revizyonlar tekrarlanır.

---

### Kayıt 1.7 — İnsan, AI'ın mimari tercihini reddediyor: Docker içinde Docker kaldırıldı

**Prompt:**

> yoo bekle uygulamayı o zaman dockerdan kaldırmayalım ben yanlış anlaşıldım. Genel olarak dependencyler dockerdan kalkması çalıştırıyorsa docker içinde docker çalışmasını istemem

**AI çıktısı — özet:**

AI, isteği şöyle yorumladı ve doğruladı: uygulama Docker'da kalacak, tüm bağımlılıklar imajın içinde olacak, host'a yalnızca Docker kurulacak — ancak **iç içe Docker olmayacak.** Sandbox artık ayrı bir konteyner değil, aynı konteyner içinde süreç düzeyinde izole edilen bir alt süreç.

Bunun bir kaybı olduğunu açıkça söyledi: ayrı konteyner gitmesiyle `--network=none` ile sağlanan **ağ ad alanı izolasyonu** da gidiyor. Konteynerin ağı olmak zorunda (LLM API'sine gidecek) ve alt süreç bunu miras alıyor.

Telafi olarak yeni bir savunma katmanı önerdi: **statik içe aktarma izin listesi.** Üretilen kod çalıştırılmadan önce taranıyor; `node:net`, `node:http(s)`, `node:child_process`, `node:fs`, `node:worker_threads`, `fetch`, `eval` ve dinamik `require` biçimleri varsa kod **hiç çalıştırılmadan** reddediliyor ve denetleyiciye kritik bulgu olarak iletiliyor. Gerekçe: üretilen oyun mantığı saf hesaplamadır, bu modüllere meşru ihtiyacı yoktur — kullanan bir çıktı ya hatalıdır ya kötücüldür.

Nihai sandbox tasarımı yedi katman: ayrıcalık düşürme (`runner` kullanıcısı), dört rlimit (CPU, bellek, süreç sayısı, dosya boyutu), duvar saati zaman aşımı, yol kısıtı, statik içe aktarma denetimi, ortam değişkeni temizliği — hepsi konteyner sınırının içinde.

`PROJECT.md` **v1.2**'ye yükseltildi. §3.3 mimari diyagramı ve sandbox bölümü baştan yazıldı, dizin yapısı tek `Dockerfile`'a indirildi, §5'e rlimit değerleri eklendi, §6'ya T2b tehdidi eklendi ve bilinen sınırlar tablosu tamamen değişti.

**Karar sahibi:** **İnsan** — AI'ın önerdiği mimarinin reddi.

**İnsan müdahalesi — bu kayıt bir denetim örneğidir:**

AI, Kayıt 1.6'da Docker soketi bağlamayı **varsayılan mod olarak önerdi.** Bunu yaparken kendi güvenlik bölümüne S1 numaralı bilinen sınır olarak şunu yazmıştı: *"soketi okuyabilen bir süreç host üzerinde root eşdeğeri yetki elde edebilir; yani app konteyneri, izole ettiği koddan daha ayrıcalıklıdır — bu bir çelişkidir."*

Yani AI, önerdiği çözümün çelişkili olduğunu **fark etti, yazdı, ama yine de varsayılan olarak önerdi.** Gerekçesi standart pratik olmasıydı ("kardeş konteyner başlatmanın standart yolu budur"). İnsan bunu reddetti.

Sonuç, iki açıdan AI'ın önerisinden iyi:

1. **Güvenlik çelişkisi ortadan kalktı.** Uygulama artık host üzerinde ayrıcalıklı değil. Kendi belgelediği S1 sınırı yok oldu.
2. **Karmaşıklık azaldı.** Tek imaj, tek konteyner, soket bağlama yok, iki kademeli mod yönetimi yok. 3 günlük süre kısıtında (K1) bu doğrudan risk azalması demek.

**Çıkarılan ders:** AI, bir çözümün bilinen sakıncasını doğru tespit edip belgeleyebilir ve buna rağmen o çözümü önerebilir — çünkü "yaygın pratik" ile "bu proje için doğru" aynı şey değildir. **AI'ın kendi yazdığı "bilinen sınırlar" bölümü, körü körüne kabul edilecek bir teslim değil, sorgulanacak bir kontrol listesidir.** Bu projede o listeye bakıp itiraz eden insan olmuştur; benzer maddeler ilerleyen günlerde de aynı gözle okunacaktır.

**Denetim notu tablosuna etkisi:** Aşağıdaki "Denetim notları" tablosuna yeni satır eklenmiştir (statik içe aktarma denetiminin atlatılabilirliği), çünkü bu da desen tabanlı ve dolayısıyla teorik olarak aşılabilir bir savunmadır.

---

### Kayıt 1.8 — Faz planı ve Faz 0: ölçüm spesifikasyonu düzeltiyor

**Prompt:**

> hadi başlayalım Proje mimari analizi ve fazlarını çıkar sonra aşama aşama başlayalım

**AI çıktısı — özet:**

İki iş yapıldı.

**(1) `docs/faz-plani.md` üretildi.** `PROJECT.md`'deki *çalışma anı* katman bağımlılığı ile *inşa sırası*nın farklı olduğu tespit edildi: inşa sırasını belirleyen şey, bir modülün test edilebilmesi için başka neyin var olması gerektiğidir. Üç sıralama ilkesi konuldu — deterministik olan önce, en riskli varsayım en ucuza, kanıt kendisini anlatan belgeden önce. 7 faz, güne dağılım, kritik yol, ve süre yetmezse hangi sırayla kapsam kesileceği (4 adımlı, en az puan kaybettiren önce) yazıldı. Faz 4'ün gerçek ön koşulunun **insan tarafından yazılacak promptlar** olduğu ve bunun kritik yolun üstüne oturtulmaması gerektiği ayrıca işaretlendi.

**(2) Faz 0 tamamlandı ve doğrulandı.** `Dockerfile` (çok aşamalı: `node:20-slim`'den yalnızca `node` ikilisi, `python:3.11-slim` üzerine), `docker-compose.yml`, `.dockerignore`, `.gitignore`, `.env.example`, `requirements.txt`, `src/config.py`, `src/orchestrator/limits.py`, `src/web/app.py`, kurulum denetimi gösteren `index.html`, `README.md`.

Ölçülen sonuçlar: imaj **464 MB** (hedef <500) · `node v20.20.2` · `runner` uid=999 · `.env` yokken `replay` moduyla açıldı · `node --test` iki testi geçti · `npm` imajda yok.

**Karar sahibi:** Faz sıralaması ve Faz 0 içeriği AI; **"önce mimari analiz ve fazlar, sonra aşama aşama"** talimatı insana ait. Bu talimat AI'ın doğrudan kod yazmaya başlamasını engelledi ve sıralamayı bir belgeye bağladı.

**İnsan müdahalesi / denetim bulgusu — spesifikasyon ölçümle çürütüldü:**

Faz 0 kapanmadan, planın "en riskli varsayımı en ucuza test et" ilkesi uygulanarak rlimit'ler fiilen ölçüldü. Sonuç:

| Katman | Sonuç |
|---|---|
| `RLIMIT_CPU` = 3 sn vs sonsuz döngü | ✅ `SIGKILL` |
| `RLIMIT_FSIZE` = 1 MB vs 50 MB yazım | ✅ yazma hatası |
| `RLIMIT_NPROC` = 32 | ✅ meşru kodu engellemiyor |
| Ayrıcalık düşürme | ✅ uid=999, `/etc`'e yazım `EACCES` |
| **`RLIMIT_AS` = 512 MB** | ❌ **meşru "hello world" bile `SIGTRAP` ile çöktü**; 128 MB'de süreç asıldı |

Sebep: V8, pointer-compression için devasa bir **sanal** adres alanı ayırır. Bu alan yerleşik bellek değildir ama `RLIMIT_AS` onu sayar. Yani `PROJECT.md` v1.2'deki `RLIMIT_AS = 512 MB` satırı uygulansaydı **sandbox, kötü niyetli kodu değil sistemin kendisini durdururdu** — üretilen her oyun testi çöker, hata da bellek limitine değil "üretilen kod bozuk" görünümüne yorulurdu. `RLIMIT_DATA`ya çevrildi; ölçümde 512 MB'de meşru kod çalışıyor, 256 MB'de sınırsız ayırma `SIGABRT` ile duruyor.

**Çıkarılan ders:** Kayıt 1.7'nin dersinin ikinci yarısı. Orada AI'ın belgelediği bir sakıncayı yine de önerdiği görülmüştü; burada ise **hiç sakınca görmediği, makul duran ve doğru terminolojiyle yazılmış bir sayının fiilen yanlış olduğu** görülüyor. `RLIMIT_AS = 512 MB` okurken hatalı görünmüyor — hata ancak çalıştırılınca ortaya çıkıyor. Bu, "kanıt, kanıtı anlatan belgeden önce gelir" ilkesinin neden bir üslup tercihi olmadığını gösteriyor: spesifikasyon ölçülmeden yazıldığında, yanlışlık belgeye doğru gibi geçiyor.

`PROJECT.md` **v1.3**'e yükseltildi. Ölçüm betiği `tests/manual/rlimit_olcumu.py` olarak saklandı — iddia artık yeniden üretilebilir.

---

### Kayıt 1.9 — Teslim biçimi kararları ve Faz 1

**Prompt:**

> teslim formatı zip dosyası olarak belirliyorum. Ama aynı zamanda versiyonlama takibi için GitHub'da private bir repo açmak istiyorum. Demo işini ben kayıt alacağım sıkıntı yok. Bireysel olarak geliştiriyorum.
>
> Faz 1 e başlayabilirsin. Benim dikkat etmem gereken şeyleri veyahut doğrulamamı istediğin şeyleri faz 1 sonrası belirtebilirsin. Eğer gerekli değilse devam edebiliriz.

**AI çıktısı — özet:**

Üç açık soru insan tarafından kapatıldı: **zip teslim + private GitHub repo** (zip teslim edilen şey, repo çalışma geçmişi), **kayıtlı demo**, **bireysel geliştirme**. Git deposu başlatıldı, Faz 0 ayrı bir commit olarak işlendi. `.gitattributes` eklendi — Windows'ta geliştirilip Linux konteynerde çalışan bir projede CRLF, temiz bir klonda derlemeyi bozabilir.

Faz 1 üretimi: `transcript/models.py` (§7'nin tamamı, pydantic), `transcript/store.py` (JSON + Markdown dışa aktarım, KK-07), `orchestrator/state_machine.py` (16 geçiş), `limits.py`'ye `BudgetTracker` (enjekte edilebilir saat), dört test dosyası + fabrikalar. **95 test, 0.38 saniye, sıfır LLM çağrısı.** Test servisi `docker compose run --rm test` olarak compose'a eklendi.

**Karar sahibi:** Teslim biçimi kararları **insan**. Faz 1 tasarımı AI.

**İnsan müdahalesi:** Doğrudan müdahale olmadı; ancak insanın "dikkat etmem gereken şeyleri belirt" talimatı, aşağıdaki iki bulgunun rapor edilmesini zorunlu kıldı.

**Denetim bulgusu 1 — test, gerçek bir hata yakaladı (Türkçe küçük harf):**

İlerleme-yok koruması red gerekçelerini karşılaştırıyor ve karşılaştırmadan önce `lower()` uyguluyordu. Python'un `lower()` metodu **'İ' harfini 'i' + birleşik nokta (U+0307) olarak açar**, dolayısıyla `"EKSİK".lower() != "eksik"`. Gerekçelerin tamamı Türkçe olduğu için bu, aynı gerekçenin farklı yazımını "yeni gerekçe" sayacak ve **KK-03'teki ilerleme-yok korumasını sessizce devre dışı bırakacaktı.** Sistem hata vermez, sadece durması gereken yerde durmaz; MAX_TUR dolana kadar boşuna tur harcardı.

Türkçe I/İ çeviri tablosu eklendi (`İ→i`, `I→ı`; kalan harfleri standart `lower()` doğru çeviriyor) ve beş yazım varyantı ile noktasız I için testler yazıldı. **Bu hatayı insan değil test yakaladı** — ve testin kendisi AI tarafından, "her koruma koşulunun hem geçen hem düşen hali sınanır" kuralı gereği yazılmıştı.

**Denetim bulgusu 2 — spesifikasyonda üç yazılmamış dal:**

`PROJECT.md` §4.2 tablosu uygulanmaya çalışılınca üç boşluk çıktı:

| Boşluk | Nasıl ortaya çıktı |
|---|---|
| G3r | Tablo "şema hatası (2. kez) → HATA" diyor; **1. kezin nereye gittiği yazılı değil.** Yeniden deneme hakkı ima ediliyor ama geçiş tanımsız |
| G9r | Aynı sorun denetleyici ayrıştırma hatasında. KK-05 "bir kez yeniden dener" diyor, tablo demiyor |
| G6s | KK-06 "sır bulunursa KABUL geçersiz sayılır ve red turu başlatılır" diyor; **bu dal geçiş tablosunda hiç yok** |

Üçü de eklendi (`PROJECT.md` v1.4). Bu, kabul kriterleri ile geçiş tablosunun **birbirinden bağımsız yazıldığında sessizce çelişebileceğini** gösteriyor: her ikisi de doğru görünüyordu, uyuşmadıkları ancak kod yazılırken anlaşıldı.

**Bilinçli olarak KAPATILMAYAN boşluk:** `karar = KABUL` iken `onem = kritik` bir bulgu varsa ne olmalı? §7.4 yalnızca test sonucu kuralını tanımlıyor. AI kendiliğinden ikinci bir iş kuralı **icat etmedi**; mevcut davranış (KABUL geçerli sayılır) `test_kritik_bulgulu_kabul_su_an_kabul_sayilir` testiyle kayda geçirildi ve karar insana bırakıldı. Gerekçe: Kayıt 1.7 ve 1.8'in dersi, AI'ın makul görünen ama doğrulanmamış kararlarının spesifikasyona sessizce sızmasının asıl risk olduğu yönünde.

---

### Kayıt 1.10 — Kapsamın ölçüte bağlanması ve rol bazlı anahtar girişi

**Prompt:**

> peki sana bir soru mesela oyun istiyoruz ya. Verdiğimiz oyunu kendisi değerlendirip bu yapılabilir yapılamaz dese mesela connect-4 oyunu dediğimizde kapsam alanı dışı olmasın bence. Buna bir RAG yapısı bağlanabilir mi sence?

> onaylıyorum haydi devam edelim. Bu arada son kullanıcının her bir agent için kendi api key'ini yerleştireceği bir alan istiyorum. (Bunun ama data leak'i önleyecek şekilde yapmamız lazım bunu da değerlendir)

**AI çıktısı — özet:**

İki ayrı iş yapıldı.

**(1) Kapsam, isim listesinden ölçüte çevrildi.** `oyun` alanı dört elemanlı bir enum'du; connect-4 bu yüzden reddedilirdi — oysa snake'ten kolaydır. §2.1.1'e beş ölçüt (U1–U5) yazıldı, `oyun` serbest ada dönüştü, planlayıcı çıktısına yapısal `uygulanabilirlik` nesnesi eklendi. Yeni son durum `KAPSAM_DISI` ve geçiş G2k: gerekçeli ret artık `HATA`dan ayrı, çünkü "sistem çöktü" ile "sistem değerlendirdi ve yapmadı" aynı şey değil.

Denetleyicideki "kendi test sonucuyla çelişemez" kuralının eşleniği planlayıcıya da kondu: `UYGUN` derken 10'dan fazla özel durum veya harici varlık ihtiyacı bildirirse karar geçersiz sayılır. **İki geçersiz kılma nedeni de mevcut spesifikasyondan türetildi** (U2 ölçütü ve §2.2'deki harici varlık yasağı); yeni kural icat edilmedi.

**(2) Rol bazlı anahtar kasası.** `security/key_vault.py` + 25 test.

**Karar sahibi:** Her iki fikir de **insana ait.** Enum'u AI yazmış ve sorgulamamıştı; sabit listenin karmaşıklık için kötü bir vekil ölçü olduğunu insan fark etti. Anahtar girişi ve "data leak'i önleyecek şekilde" kısıtı da insandan geldi.

**İnsan müdahalesi — AI'ın önerisi reddedilen kısım:**

İnsan RAG sordu. AI **hayır** dedi ve gerekçelendirdi: uygulanabilirlik bir arama değil bir yargıdır; model bu oyunların kurallarını zaten biliyor; ve 3 günde toplanacak 6–8 belge üzerinde vektör araması, o belgeleri doğrudan bağlama koymaktan kesinlikle daha kötüdür (üstüne gömme modeli, indeks, eşik gibi sessizce bozulabilecek üç parça ekler). Bunun yerine RAG'in işe yarayan kısmı — kabul kriterlerinin koşudan koşuya kaymaması — için **sürümlü kural kartı deposu** önerildi ve Faz 4'e, MCP şartını karşılayacak biçimde not düşüldü.

**Güvenlik değerlendirmesi — istenen özellik neyi açıyor:**

Anahtar girişi, sisteme üçüncü taraf kimlik bilgisi emanet etmek demek. Yedi sızıntı yolu belirlendi ve her biri için bir kural + en az bir test yazıldı: diske yazma, geri okuma, istisna izinde `repr` dökümü, sağlayıcı hata mesajının (401) transkripte yazılması, doğrulama hatasının anahtarı yankılaması, alt sürece geçme, yerel ağdan erişim.

En çok işe yarayan tasarım kararı: **`redact()` desen değil birebir dize eşleşmesi kullanıyor.** Anahtarın tam değeri bilindiği için eşleşme kesin — desen tabanlı sır taramasının bilinen belirsizliği (S3) kullanıcı anahtarları için geçerli değil. Bu, mevcut bir bilinen sınırı yeni özellik için **daraltan** bir karar.

Ayrıca konteyner portu `0.0.0.0` yerine `127.0.0.1`'e bağlandı. Arayüz artık anahtar kabul ettiği için yerel ağdaki başka makinelerden erişilebilir olmamalı.

**Dürüstçe bırakılan açık:** arayüzün önünde kimlik doğrulama yok. Anahtar girildikten sonra `localhost:8000`'e erişebilen herkes o anahtarla istek başlatabilir. Bu, tek kullanıcılı yerel çalıştırma varsayımının (V3) doğrudan sonucu ve **S5 olarak bilinen sınırlar tablosuna yazıldı** — gizlenmedi. Azaltıcılar: yerel ağa kapalı port, bellekte tutulan ve konteyner durunca kaybolan anahtar, açık temizleme eylemi.

---

### Kayıt 2.1 — Faz 2: sandbox ve güvenlik

**Prompt:**

> haydi geçelim.

**AI çıktısı — özet:**

Yedi modül: `security/{path_guard, secret_scan, input_guard}`, `sandbox/{import_guard, launcher, process_runner}`, `tools/test_runner`. İki test dosyası (`test_security.py` desen ve mantık testleri, `test_sandbox.py` gerçek süreç başlatan davranış testleri). **Toplam 221 test, ~11 saniye.**

Rubriğin güvenlik-test kalemi artık kanıtlı: T1, T2, T2b, T3, T4, T4b, T5, T6, T7, T8 tehditlerinin her biri için geçen negatif test var ve `PROJECT.md` §6 tablosundaki test sütunları gerçek test adlarıyla dolduruldu.

**Karar sahibi:** AI (Faz 2 içeriği). İnsan onayı: "haydi geçelim".

**Tasarım kararı 1 — `preexec_fn` kullanılmadı:**

Kaynak limitlerini ve ayrıcalık düşürmeyi uygulamanın standart yolu `subprocess`'in `preexec_fn` kancasıdır ve Faz 0 ölçüm betiği de onu kullanıyordu. Ancak `preexec_fn` `fork` ile `exec` arasında çalışır ve **çok iş parçacıklı bir süreçte kilitlenme riski taşır** — Python belgeleri bunu açıkça uyarıyor. Uygulama uvicorn altında koşacağı ve alt süreç bir iş parçacığı havuzundan başlatılacağı için risk gerçek.

Bunun yerine ayrı bir **fırlatıcı süreci** yazıldı (`sandbox/launcher.py`): limitleri kendi üzerine uygular, ayrıcalığı düşürür, sonra `exec` ile hedefe devreder. Kaynak limitleri `exec` sınırını aşarak korunduğu için sonuç aynı, kilitlenme riski yok. Fırlatıcı **projeden hiçbir şey içe aktarmaz** — bu sayede alt sürecin ortamı (`PYTHONPATH` dahil) tamamen temizlenebiliyor.

**Denetim bulgusu 1 — testin ortaya çıkardığı ürün eksiği:**

İlk koşuda bir test `EACCES` ile düştü: ayrıcalık düşürülen süreç, root'un açtığı workspace dizinine `stat` bile atamıyordu. Bu bir test kurgusu hatası gibi görünüyordu ama **gerçek bir ürün eksiğiydi** — üretimde de aynı şey olacaktı ve hata mesajı "üretilen kod bozuk" gibi görünecekti, gerçek sebep izin olduğu hâlde. `ProcessRunner.grant_access()` eklendi ve bilinçli olarak **yalnızca statik denetimi geçmiş kod için** çağrılıyor: reddedilen kodun dizini hiç devredilmiyor.

Ayrıca test kurgusu değiştirildi: sandbox testleri artık `tmp_path` yerine gerçek `/workspaces` altında koşuyor. Gerekçe: sandbox testinin ortamı üretimden farklı olmamalı, yoksa test yeşil olur ama üretim kırılır.

**Denetim bulgusu 2 — AI kendi yazdığı zaafı test ederken buldu (T4b):**

`parse_tap` yazılırken "üretilen kod sahte TAP özeti basarsa ne olur" sorusu akla geldi ve **mevcut davranışı kayda geçiren** bir test yazıldı: ayrıştırıcı ilk eşleşmeyi aldığı için `console.log('# pass 99')` enjeksiyonu mümkündü. Test yazılıp davranış görünür hale gelince zaafın kabul edilebilir olmadığı anlaşıldı ve iki bağımsız önlemle kapatıldı:

1. Ayrıştırıcı artık **son** özet satırını alıyor — gerçek özet çıktının sonundadır.
2. **Çıkış kodu** ayrıca kontrol ediliyor; çıkış kodu enjekte edilemez.

Bu, T4'ün (sahte KABUL) kardeşi olarak **T4b (sahte test kanıtı)** adıyla tehdit tablosuna girdi. Ders: "mevcut davranışı kayda geçiren test" yazmak, zaafı belgelemenin değil **görünür kılmanın** yolu — görünür olunca kapatılıyor.

**Hâlâ açık:** statik denetimin gizlenmiş kodla atlatılabilirliği (S2). Bu bilinçli bir sınır ve kapatılmayacak; atlatılsa dahi ayrıcalık düşürme, rlimit'ler ve konteyner sınırı devrede kalıyor.

---

### Kayıt 2.2 — Prompt'lar yazıldı; prompt ile şema arasındaki sapma

**Prompt:**

> Şimdi 3 tane md dosyasını da yazdım. Ama bakmanı istediğim bir şey var sanırım 4 oyuna fixli yazıldı. Kontrol edip seninle son konuştuğumuz contexte düzenlemeni isteyorum onları.

**AI çıktısı — özet:**

Üç prompt insan tarafından yazıldı (kural K4). AI bunları şemalara karşı denetledi, dört sapma buldu ve düzeltti; ayrıca sapmanın bir daha oluşmaması için `tests/test_prompt_ornekleri.py` yazıldı — prompt'lardaki her JSON örneği artık gerçek şemaya karşı doğrulanıyor.

**Karar sahibi:** Prompt içeriği **insan**. Denetim ve şema uyumu düzeltmeleri AI. Kapsam sorusunu ("sanırım 4 oyuna fixli yazıldı") insan tespit etti.

**Bulgular — insanın tespit ettiğinden ikisi daha ciddiydi:**

| # | Sapma | Sonucu |
|---|---|---|
| 1 | Planlayıcı kapsamı dört oyuna sabitlenmişti | İnsanın tespiti. §2.1.1 uygulanabilirlik ölçütüyle değiştirildi |
| 2 | **Planlayıcı çıktı şeması tamamen farklıydı** | `{"durum": "PLAN"...}` üretiyordu; şemada `durum` alanı yok, `uygulanabilirlik` zorunlu. `extra="forbid"` nedeniyle **hiçbir yanıtı doğrulamadan geçemezdi** |
| 3 | **Denetleyici `"düşük"` yazıyordu** | Şema `"dusuk"` bekliyor (aksansız). Enum reddi — her `dusuk` önemli bulgu yanıtı çöpe giderdi |
| 4 | Denetleyici şema örneği kendi kuralını çiğniyordu | `KABUL` derken `kalan: 1` gösteriyordu — prompt'un üç bölüm sonra "mutlak kural" dediği şeyi örnekte ihlal ediyor |

Dördüncüsünü **yeni yazılan test yakaladı**, insan da AI de gözden kaçırmıştı. Model gördüğü örneği taklit eder; bu örnek T4'ü (sahte KABUL) prompt üzerinden yeniden açardı.

**İkinci ve üçüncü maddeler neden önemli:** ikisi de "prompt doğru, kod doğru, ama birbirlerinden habersiz" kategorisinde. Prompt'ları okurken hiçbiri hatalı görünmüyor. Ancak sistem ilk kez Faz 4'te çalıştırıldığında planlayıcı **her turda** şema hatası verecek, iki denemeden sonra `HATA` durumuna düşecekti — ve hata "LLM saçmalıyor" gibi görünecekti, gerçek sebep prompt ile şemanın farklı sözleşmeler konuşması olduğu hâlde. Faz 4'te saatler kaybettirebilirdi.

**Türetilen kalıcı önlem:** `test_prompt_ornekleri.py`. Prompt'lardaki JSON örnekleri artık şemaya karşı doğrulanıyor; ayrıca planlayıcı prompt'unun hem UYGUN hem UYGUN_DEGIL örneği içermesi ve örneklerin en az birinin bilinen-iyi dört oyunun dışında olması da test ediliyor. Kural K4 prompt'ları AI'dan korur; bu test onları koddan **sapmaktan** korur.

**Kod tarafında iki sıkılaştırma:**

1. `RED` kararı artık şema düzeyinde **en az bir bulgu** gerektiriyor. Gerekçesiz red revizyon turunu boşa harcar: uygulayıcı neyi düzelteceğini bilemez, denetleyici aynı gerekçeyle tekrar reddeder ve sistem ilerleme-yok tespitiyle durur. İnsanın prompt'unda bu kural zaten yazılıydı — şemaya da taşındı.
2. **`test_sonucu` ölçülür, beyan edilmez** (yeni orkestratör kuralı, Faz 4'te uygulanacak). Mevcut hâliyle §7.4'ün çelişki denetimi denetleyicinin kendi bildirdiği sayıya bakıyordu; denetleyici `kalan: 0` yazarak denetimi atlatabilirdi. Artık orkestratör `TestRunner`ın ölçtüğü değeri yerine koyacak. Denetleyici prompt'u da bunu açıkça bildiriyor.

**Doğrulanan tasarım tercihi:** insanın seçtiği CommonJS modül deseni (`module.exports` guard + düz `<script>` etiketi) sandbox'ta fiilen çalıştırıldı — 2/2 test geçti, statik denetim temiz. Tahmin edilmedi, ölçüldü.

**Yan bulgu:** doğrulama sırasında `TestRunner` olmayan bir dizin için `calistirildi: True` döndürüyordu. Güvenli tarafta bir hataydı (`kalan = 1`) ama transkripte yanıltıcı bir kayıt yazardı; düzeltildi.

---

### Kayıt 2.3 — U4 ölçütünün daraltılması ve oyun kütüphanesi

**Prompt:**

> dikkatimi çeken tek şey plannerda uygulanabilirlikte ses dosyası gereksinimi. Burasını pek anlamadım. Şimdi misal flappy bird yap desem normalde her tıklamada ses çıkıyor sırf bunun yüzünden uygulanamaz mı diyecek? Bir de öyle bir ayarlayalım ki mesela ilk oyun yapıldı onu kaydetsin arkasına ikinci bir oyun girdiğimizde onu de yeni bir dosyaya hazırlasın ve hazır olan oyunlar arasında geçiş sağlayabilelim.

**AI çıktısı — özet:**

İki iş. (1) U4 ölçütü yeniden yazıldı. (2) `transcript/library.py` + üç API ucu + arayüzde oyun listesi; 28 yeni test.

**Karar sahibi:** Her iki tespit de **insana ait.**

**Denetim bulgusu — ölçüt yanlış ifade edilmişti:**

U4 "harici varlık (görsel, ses, veri dosyası) gerekiyor mu" diye yazılmıştı. İnsanın sorusu ölçütün hatalı olduğunu ortaya çıkardı: **flappy bird'ün tıklama sesi bir dosya gerektirmez** — Web Audio osilatörüyle üretilir, saf koddur. Ölçütün asıl kaynağı §2.2'deki tek dosyalık teslim kısıtıdır, "ses olmasın" kuralı değil.

Bu, AI'ın yaptığı bir **soyutlama hatasıydı**: gerçek kısıt ("yanında başka dosya taşınmasın") yerine onun bir sonucu ("harici varlık olmasın") ölçüt olarak yazılmış, sonuç da kaynaktan geniş kalmıştı. Kimse fark etmeseydi flappy bird, asteroids, space invaders gibi kapsam içi olması gereken oyunlar yalnızca ses ürettikleri için reddedilecekti — ve ret **gerekçeli** olacağı için makul bile görünecekti.

U4 artık "harici varlık **dosyası**" diyor ve prompt'a somut bir sınama sorusu eklendi: *"Bu oyun tek bir HTML dosyası olarak, yanında başka hiçbir dosya olmadan teslim edilebilir mi?"* Flappy bird örneği de prompt'a kapsam içi örnek olarak girdi.

**Tasarım kararı — kütüphane ayrı indeks tutmaz:**

Oyun listesi bir `index.json` dosyasında değil, her görevin kendi `transkript.json` dosyasından türetiliyor. Gerekçe: iki kayıt olsaydı ikisi sapabilirdi. Tek kaynak, sapma imkânsız. Yarım kalmış koşuların artıkları (transkripti olmayan dizinler) listelenmiyor — oynanabilir bir oyunmuş gibi görünmemeliler.

**Yeni saldırı yüzeyi ve kapatılması:** görev kimliği artık **URL yolundan** geliyor. İki katman kondu: dosya adı izin listesi (`game.html`, `logic.js`, `logic.test.js`, `transkript.json`, `transkript.md`) ve yol koruması. `../gizli`, `/etc/passwd`, `g-001/../../kacis` gibi denemeler test edildi ve canlı sistemde de 404 döndüğü doğrulandı.

**Denetim bulgusu 2 — süreç sandbox'ı tarayıcıyı kapsamıyor (T2c):**

Oyunu iframe'e koyarken fark edildi: `PROJECT.md` §3.3'teki yedi katman **yalnızca test alt sürecini** koruyor. `game.html` eğitmenin tarayıcısında çalışıyor ve orada rlimit de, ayrıcalık düşürme de, statik içe aktarma denetimi de yok — üstelik `game.html` zaten statik denetimden muaf tutulmuştu (tarayıcıda çalışır gerekçesiyle). Yani sistemin en dikkatle korunan tarafı testler, en az korunan tarafı ise kullanıcının fiilen çalıştırdığı şeydi.

Sunum katmanında kendi kısıtı kuruldu: `connect-src 'none'` (ağ çıkışı yok), `img-src data:` (uzak görsel URL'si de bir sızıntı kanalıdır), `form-action 'none'`, ve iframe `sandbox="allow-scripts"`.

İlk denemede iframe'e `allow-same-origin` de verilmişti. Bu **sessiz bir baypastı**: aynı kaynağı paylaşan bir iframe ana sayfayı script'leyebilir ve onun ağ erişimini kullanarak kendi CSP'sini atlatabilirdi. Kaldırıldı. Kaldırınca ikinci bir sorun çıktı — belge opak kaynağa düştüğü için `script-src 'self'` sunucuya çözülmüyor ve `logic.js` engelleniyordu; CSP'ye sunucu kaynağı açıkça yazıldı.

**Doğrulanmayan, doğrulanacak:** CSP ve iframe kısıtlarının birlikte çalıştığı **tarayıcıda görsel olarak** teyit edilmeli. HTTP başlıkları doğrulandı (`curl` düzeyinde), ancak "oyun iframe'de gerçekten açılıyor mu" sorusu ancak sayfa açılarak yanıtlanır. Denetim tablosuna eklendi.

---

### Kayıt 2.4 — Tarayıcı doğrulaması ve analiz dokümanı

**Prompt:**

> evet doğrulamayı sağladım. kazanan: X sonucu veriyor. Gerekli commitleri ve analiz raporlarını ve AI günlüğünü güncellemediysen güncelle. Sonrasında devam edebiliriz.

**AI çıktısı — özet:**

İnsan tarayıcı doğrulamasını yaptı; denetim tablosundaki son açık satır kapandı. `docs/analiz.md` yazıldı: 12 user story, **24 Given/When/Then kabul kriteri**, uygulanabilirlik ölçütü, varsayım/kısıt/risk tabloları ve **izlenebilirlik matrisi**. Faz planına gerçekleşen durum tablosu eklendi.

**Karar sahibi:** İnsan — hem doğrulama hem "eksik teslim var mı" kontrolü. AI, analiz dokümanının hâlâ yazılmamış olduğunu bu istek üzerine fark etti.

**Süreç bulgusu — teslim kaymıştı:**

`docs/analiz.md` **zorunlu beş teslimden biri** ve eksikliği projeyi değerlendirme dışı bırakıyor (K2). Faz planında 1. güne önerilmiş, sonra Faz 6'ya kaymış ve orada unutulmuştu. İki gün boyunca hiçbir kontrol bunu yakalamadı çünkü **fazlar kod üretimine göre sıralanmıştı, teslimlere göre değil.** İnsanın "analiz raporlarını güncelledin mi" sorusu olmasa 3. güne kalırdı.

Faz planına "gerçekleşen" tablosu eklenerek kalan zorunlu teslimler açıkça listelendi: teknik doküman, kullanım kılavuzu, demo. Ders: **faz planı ilerlemeyi gösteriyor ama eksiği göstermiyordu**; bir plan neyin yapıldığını değil neyin kaldığını görünür kılmalı.

**Doğrulamanın kime ait olduğu:** iframe + CSP kombinasyonunun çalıştığını AI ölçemezdi — tarayıcı davranışı süreç dışındadır. Denetim tablosuna "insan tarafından doğrulandı" olarak yazıldı. Projede bu, ölçümün AI'dan insana devredildiği ikinci nokta (ilki eğitmen makinesinde `docker compose up`).

**İzlenebilirlik matrisi neden yazıldı:** 24 kabul kriterinin her biri bir test adına bağlandı. Rubrikteki analiz ve test kalemlerinin ikisini de aynı tabloyla karşılıyor, ama asıl faydası şu: kriteri olup testi olmayan bir madde artık tabloda **boş görünür**. Bugün boş satır yok.

---

### Kayıt 3.1 — Faz 3: sağlayıcı katmanı ve kayıt/oynatma

**Prompt:**

> haydi geçelim

**AI çıktısı — özet:**

Yedi modül: `provider.py` (sözleşme + istek parmak izi), `pricing.py`, `factory.py` (rol bazlı çözümleme), Anthropic, OpenAI, Ollama ve `replay_provider`. Anahtar uçları (`/api/anahtarlar`) bağlandı, sağlık ucu rol yapılandırmasını gösteriyor, arayüze anahtar giriş paneli eklendi. **315 test.**

**Karar sahibi:** AI. İnsan onayı: "haydi geçelim".

**SDK bağlamaları tahmin edilmedi.** Kod yazmadan önce `claude-api` becerisinin Python referansı okundu. Doğrulanan noktalar: `messages.stream()` bağlam yöneticisi + `get_final_message()`, `cache_control` için sistem promptunun **liste biçiminde** verilmesi gerektiği, Opus 5'te `budget_tokens` gönderilirse 400 döndüğü ve `{"type": "adaptive"}` yazılması gerektiği, yanıt içeriğinin blok listesi olduğu ve `thinking` bloklarının ayıklanması gerektiği. Bunların en az ikisi hafızadan yazılsaydı yanlış olurdu.

**Tasarım kararı 1 — maliyet yukarı yuvarlanır:**

`estimate_cost` bilinmeyen bir model kimliği için **en pahalı bilinen fiyatı** kullanıyor. İlk sezgi "bilinmiyorsa sıfır" yazmaktı; bu, `MAX_MALIYET_USD` tavanını sessizce devre dışı bırakırdı — yeni bir model kimliği girilir girilmez harcama sınırsız olurdu. Aynı gerekçeyle Sonnet 5'in 31.08'e kadar geçerli tanıtım fiyatı ($2/$10) yerine liste fiyatı ($3/$15) yazıldı: tavan hesabı gerçek maliyetin **üstünde** kalmalı.

**Tasarım kararı 2 — OpenAI SDK'sı çıkarıldı:**

Anthropic tarafında SDK'nın soyutlamaları gerçekten kullanılıyor (akış, önbellek, düşünme blokları). OpenAI tarafında ise tek bir çağrı şekli var. Tek çağrı için büyük bir istemci bağımlılığı taşımanın karşılığı yok; belgelenmiş REST ucu `httpx` ile kullanıldı. Ölçülen sonuç: imaj **464 → 438 MB**.

İkincil fayda: `openai` paketinin 3.x sürümünde çağrı şeklinin ne olduğundan emin değildim ve referansım yoktu. Tahmin ederek SDK kodu yazmak yerine, sözleşmesi kararlı olan REST ucunu kullanmak dürüst olanıydı.

**Tasarım kararı 3 — kaset eksikse uydurulmaz:**

`ReplayProvider` kaset bulamazsa `CassetteMissing` fırlatıyor. Alternatif, makul görünen bir sahte yanıt üretmekti — ama o zaman test yeşil olur ve neyi kaçırdığı görünmezdi. Aynı ilkeyle kasete sistem promptunun tam metni değil hash'i yazılıyor: prompt dosyaları zaten depoda sürümlü, ikinci kopya senkronizasyon riski.

**Denetim bulgusu — testin bulduğu güvenlik açığı:**

`test_gecersiz_rol_reddedilir` testi `sistem` rolü için anahtar göndermeyi denedi ve **200 aldı**. Şema `Role` enum'unu kabul ediyordu, `sistem` de o enum'un üyesiydi. Sonuç: hiçbir zaman kullanılmayacak bir sır bellekte tutulabiliyordu — `sistem` rolü LLM'e gitmez, durum geçişlerini kaydeder.

Düzeltme **uç noktada değil kasa katmanında** yapıldı (`KeyVault.set` artık `AGENT_ROLES` dışını reddediyor), çünkü kasayı çağıran başka bir yol da aynı hatayı yapabilirdi. Uç nokta düzeltmeyi miras aldı.

**Denetim tablosuna etkisi:** token tahminleri satırı hâlâ açık — gerçek ölçüm Faz 4'te ilk uçtan uca koşuyla gelecek. Maliyet hesabı artık var ama **hiç gerçek çağrı yapılmadı**; `pricing` fonksiyonunun doğruluğu birim testlerle sınandı, gerçek fatura ile karşılaştırılmadı.

---

### Kayıt 3.2 — Faz 4: sistem ilk kez gerçekten çalıştı

**Prompt:**

> anthropic ve openAI keyleri girdim. Anthropicte 4.93 dolar, OpenAI da 3.71 dolar var. Sen denediğinde ben sana maliyetleri rahatlıkla söyleyebilirim.

**AI çıktısı — özet:**

Faz 4 tamamlandı: gerçek MCP sunucusu (stdio, JSON-RPC 2.0), üç agent, ana döngü, görev yürütücüsü ve HTTP uçları. **352 test.** Ardından **üç gerçek koşu** yapıldı.

**Karar sahibi:** İnsan — anahtarları sağladı ve harcamaya izin verdi. Maliyet tavanı $1.00'dan **$0.40'a** çekildi: bakiye $4.93 idi, varsayılan tavan tek koşuda bakiyenin %20'sini riske atıyordu.

### Gerçek koşu sonuçları (15.08.2026)

| Görev | Sonuç | Tur | Süre | Maliyet |
|---|---|---|---|---|
| tic-tac-toe | `KABUL_EDILDI` | 1 | ~85 sn | **$0.221** |
| connect-4 | `KABUL_EDILDI` | 1 | ~90 sn | **$0.179** |
| satranç | `KAPSAM_DISI` | 1 | ~15 sn | **$0.012** |

**Toplam harcama: $0.41.** Üretilen oyunlar sırasıyla 12 ve 9 test geçirdi; testler sandbox'ta ayrıcalıksız kullanıcı olarak bağımsızca yeniden koşuldu.

### Denetim tablosundan kapanan dört satır

1. **Token tahmini 4 kat yüksekti.** 30.000 girdi / 12.000 çıktı tahmin edilmişti; gerçek 7.377 / 6.304. Tahmin muhafazakâr yöndeydi, yani zararsız — ama yine de tahmindi ve öyle işaretlenmişti.
2. **Maliyet tahmini tuttu.** $0.18–0.45 bandı öngörülmüştü; gerçek $0.179–0.221.
3. **"Satranç çok zor" iddiası kanıta dönüştü.** Sistem satrancı reddetti ve **24 özel durum** sayarak gerekçelendirdi. İddia artık AI'ın tahmini değil, sistemin ürettiği ölçüm.
4. **Uygulanabilirlik ölçütü listeden üstün çıktı.** connect-4 — eski dört oyunluk listede **olmayan** bir oyun — tek turda üretildi ve oynanabilir oldu. Ölçüt hem açtı hem kapattı.

Dördüncüsü özellikle önemli: bu değişikliği öneren insandı (Kayıt 1.10), AI enum'u yazmış ve sorgulamamıştı. Öneri artık çalışan bir kanıta sahip.

### Gözlem — prompt önbelleği beklenenden çok işe yaradı

Planlayıcının **ücretli girdi token'ı 74**. Sistem promptu (~2.500 token) önbelleğe yazıldı ve ücretlendirme oradan yapıldı. İkinci ve sonraki koşularda okuma katsayısı 0.1x olduğu için planlayıcı çağrısının girdi maliyeti neredeyse sıfırlanacak.

### Tasarım kararı — MCP gerçekten yazıldı

Sunumun "en az bir MCP çağrısı" şartı, bir Python fonksiyonuna "MCP" adı vererek değil, **ayrı süreçte konuşan bir stdio sunucusuyla** karşılandı: `initialize` el sıkışması, `tools/list`, `tools/call`. Kapsam dışı yöntemler (`resources/*`, `prompts/*`) dürüstçe `-32601` döndürüyor ve bunun tam bir MCP sunucusu **olmadığı** dosyanın başında yazılı.

Yol koruması bilinçli olarak **sunucunun içine** kondu, istemciye değil: uygulayıcı agent `../../etc/passwd` isterse reddeden taraf sunucu olmalı. Güvenlik kontrolü çağırana güvenmemelidir.

### Tasarım kararı — uygulayıcının çıktısı ile kaydı ayrıldı

LLM `{"dosyalar": {...}}` döndürüyor; transkripte yazılan `ImplementerContent` ise dosyalar **MCP üzerinden yazıldıktan sonra** üretiliyor: hangi yol, kaç bayt, hangi hash, hangi araç çağrıları. Transkript "model ne dedi"yi değil **"fiilen ne oldu"yu** kaydediyor. Model bir dosya döndürüp yazım başarısız olsaydı, kayıt bunu gösterirdi.

### Denetleyicinin beyanı hâlâ kullanılmıyor

§7.4'teki orkestratör kuralı uygulandı: denetleyicinin döndürdüğü `test_sonucu`, `TestRunner`ın ölçtüğü değerlerle **değiştiriliyor**. Bir testte denetleyici `gecen: 99, kalan: 0` beyan etti; kayda geçen değer ölçülen değer oldu ve karar RED'e çevrildi.

---

### Kayıt 3.3 — İnsan testi, 352 otomatik testin bulamadığını buldu

**Prompt:**

> tic-tac-toe sorunsuz çalıştı. connect-4 da tek sıkıntı sıra kırmızıdayken sarı yerleştirme yapıyor. Sarı renkle kırmızı rengi karıştırmış kazanma prensibi de aslında sarı kazandığında kırmızı kazandır diyor. Onun dışında gerçekten çalışıyor genel business logic. Bunları analizler ve günlüğe yazıp devam edelim.

**AI çıktısı — özet:**

Rapor olduğu gibi kabul edilmedi, üretilen kod okunarak teşhis doğrulandı. Hata `game.html` satır 61'de:

```js
const renkler = { K: '#ffeb3b', S: '#f44336' };   // K=kırmızı → sarı, S=sarı → kırmızı
```

**Karar sahibi:** İnsan — hatayı **oyunu oynayarak** buldu.

### Teşhis: sistem doğru çalışmış, denetleyici haklıymış

| Katman | Durum |
|---|---|
| `logic.js` | Doğru. Renk kavramından **tamamen habersiz**, işaretler üzerinde genel yazılmış |
| `logic.test.js` | 9 test, planın 7 kabul kriterinin tamamını anlamlı biçimde doğruluyor |
| `game.html` | **Hata burada** — ve boru hattında burayı doğrulayan hiçbir kapı yok |

Denetleyicinin gerekçesi okunduğunda tamamı `logic.js` hakkında: "yedi kabul kriterinin tamamı anlamlı assertion'larla doğrulanıyor… logic.js DOM'a hiç dokunmuyor". **Denetleyici yanlış bir şey söylemedi.** Kendisine verilen görevi eksiksiz yaptı.

### Asıl bulgu: boşluk kazara değil, yapısal

Nedensellik zinciri şu:

1. Planlayıcı prompt'u kriterleri "`node:assert` ile tek satırda test edilebilir" olacak şekilde yazmaya zorluyor — ki bu **iyi bir kural**, kriterlerin kalitesi buradan geliyor.
2. Ama aynı kural, `game.html` ile ilgili hiçbir şeyin kabul kriteri **olamayacağını** garantiliyor: canvas çizimi assert edilemez.
3. Denetleyici prompt'u estetiği denetlemiyor — doğru bir kısıt.
4. "K hangi renk" sorusu **estetik gibi görünüyor**, oysa anlamsal bir eşleme.

Yani sunum katmanı, iki doğru kuralın arasında kalan bir boşluğa düşüyor. Kimse hata yapmadı; sınır yanlış yerden geçiyordu.

### Sınırın doğru yeri

`PROJECT.md` §10.1 olarak yazıldı. Ayrım "mantık / sunum" değil şu olmalı:

| Kategori | Nereye ait | Test edilebilir |
|---|---|---|
| Kural, durum, kazanma koşulu | `logic.js` | ✔ |
| **İşaret → oyuncu/renk/etiket eşlemesi** | **`logic.js`** | ✔ |
| Çizim, ölçü, animasyon, renk tonu | `game.html` | ✖ kabul edilen sınır |

`logic.js` eşlemeyi dışa aktarsaydı (`OYUNCULAR = { K: {ad:'Kırmızı', renk:'#f44336'} }`) hem `game.html` oradan okurdu hem de ters yazım bir testle yakalanırdı.

### Neden düzeltmeyi AI yapmıyor

Çözüm prompt değişikliği gerektiriyor ve kural K4 gereği prompt'lar insana ait. İki aday `docs/analiz.md` A5 maddesine yazıldı; karar insanda. Kod tarafında yapılabilecek bir düzeltme yok — bu bir talimat sorunu, mekanizma sorunu değil.

### Bu kaydın denetim değeri

Projede **352 otomatik test** var ve hiçbiri bunu bulamazdı, çünkü hepsi doğrulanan katmanı doğruluyor. Bulan şey beş dakikalık insan oyunu oldu.

Rubrikteki "AI kullanım olgunluğu" için asıl gösterilecek nokta bu: sistemin garantisi göründüğünden **dar**. "Testler geçti" ile "oyun doğru" aynı şey değil, ve bu proje ikincisini hiçbir zaman iddia etmemeliydi. Şimdi etmiyor — S6 ve R7 olarak yazılı.

---

### Kayıt 3.4 — Faz 5 ve yalnızca OpenAI ile koşu

**Prompt:**

> Faz 5 te sadece 1 koşu daha yapmanı istiyorum. Hatta Bu sefer sadece OpenAI key kullan.

**AI çıktısı — özet:**

Faz 5 arayüzü: sohbet kutusu, **SSE ile canlı transkript**, oyun oynatıcı, kütüphane ve katlanabilir ayarlar paneli. `/api/gorev/akis` ucu eklendi. Ardından üç rolün tamamı OpenAI'a alınarak tek koşu yapıldı.

**Karar sahibi:** İnsan — hem koşu sayısını (1) hem sağlayıcıyı belirledi.

### Sonuç: sağlayıcı değişimi gerçekten tek satır

| | Anthropic (tic-tac-toe) | OpenAI (snake) |
|---|---|---|
| Sonuç | `KABUL_EDILDI`, 1 tur | `KABUL_EDILDI`, 1 tur |
| Süre | ~85 sn | ~40 sn |
| Girdi / çıktı token | 7.377 / 6.304 | 13.141 / 5.126 |
| Test | 12 geçti | 5 geçti |
| Kod değişikliği | — | **sıfır** |

`LLM_PROVIDER=openai` ve `MODEL_*=gpt-5.4` dışında hiçbir şeye dokunulmadı. §8.2'deki "orkestratör hangi sağlayıcının çalıştığını bilmez" iddiası artık ölçülmüş.

Girdi token farkı (7.377 → 13.141) prompt önbelleğinden geliyor: Anthropic tarafında ~2.500 token'lık sistem promptu önbelleğe alınıyor, OpenAI sağlayıcısında böyle bir mekanizma kullanılmıyor.

### Model kimliği tahmin edilmedi

`gpt-4o`, `gpt-5` gibi bir isim varsayıp göndermek yerine hesabın `/v1/models` ucu soruldu. Listede `gpt-5.6`'ya kadar modeller çıktı; `gpt-5.4` seçildi. Tahmin edilseydi büyük olasılıkla eski bir kimlik kullanılacaktı.

### Denetim bulgusu — şişirilmiş maliyet teslim edilecek belgeye giriyordu

`pricing.py` bilinmeyen bir model için **en pahalı bilinen tarifeyi** uyguluyor. Bu, harcama tavanı açısından doğru bir muhafazakârlık (Kayıt 3.1). Ancak `gpt-5.4`'ün fiyatı tabloda yok, dolayısıyla transkripte **$0.388 gibi kesin görünen ama gerçekte üst sınır olan** bir rakam yazılacaktı — ve transkript teslim edilen bir belge.

Aynı sayı iki farklı işi görüyordu ve birinde doğru, diğerinde yanıltıcıydı. Ayrıştırıldı: `Usage.fiyat_bilinen` eklendi ve fiyatı bilinmeyen model kullanıldığında transkripte `maliyet_ust_sinir` sistem mesajı yazılıyor. Tahmin değişmedi, **tahmin olduğu görünür oldu.**

**Sonradan doğrulama (insan raporu):** koşunun gerçek maliyeti ≈ **$0,10**, yani üst sınır (~$0,388) **yaklaşık 4 kat** yüksekmiş. Muhafazakârlık işini gördü — tavan aşılmadı, koşu yarıda kesilmedi.

`pricing.py`'ye tahminî bir `gpt-5.4` fiyatı **eklenmedi.** Rakam yaklaşık ("sanırım") ve fatura henüz yansımamıştı; toplam maliyetten geriye doğru token fiyatı türetmek, doğrulanmamış bir sayıyı harcama tavanını besleyen bir tabloya yazmak olurdu. Bu, projenin Kayıt 1.8'den beri kaçındığı hatanın aynısıdır: makul görünen, doğru terminolojiyle yazılmış, ama ölçülmemiş bir değer. Fiyat kesinleşirse tabloya girer; o zamana kadar üst sınır ve uyarı mesajı yerinde kalır.

### Yakalanan yapılandırma hatası

İlk denemede sağlayıcı `openai`'a geçti ama model `claude-opus-5` kaldı — `MODEL_*` değişkenleri `docker-compose.yml`'de geçirilmiyordu. Koşu başlatılsaydı OpenAI'a Claude model kimliği gidecek ve anlamsız bir hata alınacaktı. Sağlık ucundaki rol tablosu bunu koşudan önce gösterdi; geçişler eklendi.

Küçük bir olay ama sağlık ucunun neden **modeli de** raporladığını doğruluyor: yapılandırma hatası çalışma anında değil, bakışta görülmeli.

---

### Kayıt 4.1 — Faz 6 belgeleri ve ok tuşu sorunu

**Prompt:**

> snake inanılmaz iyi olmuş. OpenAI sanırım totalde 0.1 dolar harcadı ama hala total bakiyem 3.71

> bir tek ok tuşlarıyla oynatınca bütün uygulamada da aşağı yukarı gidiyor. Bu agentların yazdığıyla pek alakalı olduğunu sanmıyorum uygulamalık bir durum. Belki oyunları bir pop-up la ya da subdirectoryle daha full screene yakın çalıştırabiliriz

**AI çıktısı — özet:**

`docs/teknik.md` ve `docs/kilavuz.md` yazıldı — zorunlu beş teslimden ikisi. Ayrıca ok tuşu sorunu düzeltildi.

**Karar sahibi:** İnsan — hem maliyet doğrulaması hem hata raporu hem çözüm önerisi (tam ekran / ayrı pencere) ondan geldi.

### Maliyet doğrulaması: tahmin 4 kat şişikmiş

OpenAI koşusunun gerçek maliyeti ≈ **$0,10**; sistem ≤$0,388 raporlamıştı. Muhafazakârlık işini gördü, tavan aşılmadı.

`pricing.py`'ye tahminî bir `gpt-5.4` fiyatı **eklenmedi** — gerekçe Kayıt 3.4'te.

### Ok tuşu teşhisi: kullanıcı doğru söyledi

"Uygulamalık bir durum" tespiti isabetli. Sebep: iframe odakta değilken ok tuşları ana belgeye gidiyor ve sayfayı kaydırıyor. Üretilen oyunun kodu bunu düzeltemez — odak onun dışında.

Üç katmanlı düzeltme: yükleme biter bitmez iframe'e odak verildi, `tabindex` ve görünür odak halkası eklendi, **tam ekran** ve **yeni sekmede aç** düğmeleri kondu.

**Güvenlik takası açıkça yazıldı.** Tam ekran iframe sandbox'ını **korur** — oyun hâlâ `allow-scripts` kısıtı ve CSP altında. Yeni sekme ise sandbox'sız çalışır; koruma yalnızca sunucunun gönderdiği CSP'dir (ağ çıkışı ve form gönderimi kapalı). Bu yüzden birincil düğme tam ekran, ikincisi yedek.

**Prompt tarafına düşen pay:** üretilen oyunun ok tuşlarında `preventDefault()` çağırması da beklenirdi. Bu uygulayıcı prompt'una eklenebilecek bir madde ve kural K4 gereği insana ait — `analiz.md` A5'in yanına not düşüldü.

### Belgelerde bilinçli bir seçim

`kilavuz.md` §9, sistemin garantisinin dar olduğunu **kullanıcıya doğrudan söylüyor**: "KABUL_EDILDI testler geçti demektir, oyun her açıdan doğru demek değildir. Üretilen oyunu birkaç dakika oynayın."

Bir kullanım kılavuzunun ürünü övmesi beklenir; burada tersi yapıldı çünkü connect-4 olayı bunun gerçek bir risk olduğunu gösterdi. Kılavuz sınırı gizleseydi, kullanıcı aynı hatayı yaşayıp sisteme güvenini kaybederdi.

**Ekran görüntüleri eksik.** Kılavuzda dört yer `📸` ile işaretli; bunları AI üretemez, insanın alması gerekiyor.

---

### Kayıt 4.2 — Kullanıcı bir hata buldu: sağlayıcı değişiyor, model değişmiyor

**Prompt:**

> Öncelikle transkriptleri kaydetmek istiyorum böylelikle transkript geçmişinden nerde neler olmuş görebileceğim. İkincisi claude opus ve sonnet 5 kullanmak biraz fazla maliyetli ama sorun değil. Üçüncüsü api key girdisi var iyi hoş ama agent sağlayıcıları anthropic claude opus 5 sonnet 5 diye sabit duruyor openAI apisi girince hiçbir şey değişmiyor. Bunları da seçeceğimiz modele göre alt modellerinin olduğu bir katalog olsa ve biz oradan seçip kaydetsek çok çok daha faydalı ve işin sonunda maliyeti de çok düşürebiliriz diye düşünüyorum.

**Karar sahibi:** İnsan — üç isteğin üçü de ondan. Üçüncüsü bir özellik isteği gibi ifade edilmişti ama altından **hata** çıktı.

### Bulgu: bu bir eksik değil, bozukluk

`ROLE_DEFAULT_MODEL` tek bir tabloydu ve hep Claude modellerini veriyordu. `resolve_role` anahtara bakıp **sağlayıcıyı** değiştiriyor, ama modeli o tablodan alıyordu. Sonuç: yalnızca OpenAI anahtarı giren bir kullanıcı `openai` + `claude-opus-5` yapılandırması alıyor ve ilk çağrıda patlıyordu.

**Neden hiçbir test yakalamadı:** `test_provider.py::test_roller_farkli_saglayici_kullanabilir` yalnızca `config.saglayici` alanını kontrol ediyordu, `config.model` alanına bakmıyordu. Test doğru şeyi sınıyordu ama **yeterince** sınamıyordu.

**Neden ben fark etmedim:** kendi OpenAI koşumda (Kayıt 3.4) `MODEL_*` ortam değişkenlerini elle vermiştim. O anda "compose'dan geçmiyormuş" diye bir yapılandırma eksiği olarak not ettim ve geçtim — oysa asıl soru "hiç vermeseydim ne olurdu" idi. Elle düzelttiğim şey, düzeltilmesi gereken şeyin belirtisiydi.

Bu, projedeki üçüncü "AI kendi geçici çözümüyle hatanın üstünü örttü" örneği. Öncekiler Kayıt 1.8 (`RLIMIT_AS`) ve Kayıt 2.1 (`grant_access`).

### Düzeltme

`PROVIDER_DEFAULT_MODEL` sağlayıcı bazlı hale getirildi. OpenAI için hesabın hangi modellere eriştiği bilinemediğinden varsayılan **yedek** olarak işaretleniyor (`model_kaynagi`) ve arayüz katalogdan seçmeye yönlendiriyor. Tahmin bir kimlik uydurmak yerine, tahmin olduğunu söylüyor.

`test_selection.py` içinde ilk test doğrudan bu hatayı hedefliyor:
`test_openai_anahtari_claude_modeli_secmez`.

### Katalog — sabit liste tutulmadı

`GET /api/modeller` sağlayıcının kendi `/v1/models` ucundan canlı liste çekiyor. Sabit liste iki yüzden yanlış olurdu: modeller zamanla kaybolur, ve **hangi modellere erişildiği hesaba göre değişir**. Fiyatı bilinenler etikette gösteriliyor (`Claude Sonnet 5 · $3/$15 /MTok`), bilinmeyenler açıkça öyle işaretleniyor.

### Seçim diske yazılıyor, anahtar yazılmıyor

Bilinçli bir asimetri. Anahtar sırdır; bellekte durur, konteyner durunca kaybolur (§3.3). Model seçimi tercihtir; her açılışta yeniden sorulması gereksiz sürtünmedir. `data/model-secimleri.json` bu yüzden var ve `test_secim_dosyasi_anahtar_icermez` ikisinin karışmadığını sınıyor.

Ayrıca seçim **yalnızca aynı sağlayıcı için** geçerli: Anthropic için seçilen model OpenAI'a gönderilemez — düzeltilen hatanın tekrar açılmaması için.

### Maliyet: istek karşılandı ve ölçüldü

Kullanıcı "maliyeti çok düşürebiliriz" dedi; ölçülen tic-tac-toe koşusundan hesaplanan sonuç onu doğruluyor:

| Kurulum | Koşu başına |
|---|---|
| Varsayılan (Opus/Sonnet/Opus) | $0,221 |
| Dengeli (Opus/Haiku/Sonnet) | ≈$0,12 |
| Ekonomik (Sonnet/Haiku/Sonnet) | ≈$0,08 |

Kılavuza bir uyarıyla birlikte yazıldı: **planlayıcı güçlü kalmalı**, çünkü kötü bir kabul kriteri uygulayıcı ve denetleyici ne kadar iyi olursa olsun kötü bir oyun üretir. Maliyet kısmanın ucuz yeri uygulayıcıdır, planlayıcı değil.

### Transkript geçmişi

Transkriptler zaten her görev dizininde JSON+Markdown olarak duruyordu; eksik olan **görüntüleme**ydi. Kütüphanedeki her kayda "transkript" düğmesi eklendi: görev metni, son durum, hangi geçiş kuralıyla bitildiği, toplam token/maliyet, **prompt sürüm hash'leri** ve tüm agent mesajları. Reddedilen koşular da listede — neyin neden olmadığını görmek için.

Yeni bir depolama katmanı yazılmadı; var olan dosya sunumu ve izin listesi yeterliydi.

---

## Sonraki kayıt

Kayıt 4.3'te demo hazırlığı ve teslim paketi işlenecek.
