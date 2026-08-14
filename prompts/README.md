# prompts/

Bu dizindeki `.md` dosyaları **insan tarafından yazılır.** Eğitim kuralı K4
(`PROJECT.md` §2.4) gereği projedeki her şey AI'a bırakılabilir, promptlar
hariç.

## Kurallar

| Kural | Detay |
|---|---|
| Adlandırma | `<rol>.v<n>.md` — örn. `planner.v1.md` |
| Sürümleme | Prompt değişince **yeni dosya** açılır; eskisi silinmez |
| Hash | Yüklenen dosyanın sha256'sının ilk 12 hanesi her agent mesajında taşınır |
| Değişmezlik | Agent'lar çalışma anında kendi veya birbirinin promptunu değiştiremez |
| Görev metni | Kullanıcı görevi prompta gömülmez; ayrı, sınırlandırılmış veri bloğu olarak iletilir (§6/T3) |

## Gereken dosyalar

- `planner.v1.md` — görevi adımlara ve **test edilebilir kabul kriterlerine** böler
- `implementer.v1.md` — `logic.js`, `logic.test.js`, `game.html` üretir
- `reviewer.v1.md` — testi çalıştırır, **yapısal JSON** ile KABUL/RED döner

Şema ayrıntıları: `PROJECT.md` §7.2–7.4.
