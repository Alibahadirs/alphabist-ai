# Değişiklik günlüğü

## 0.91.0 - 2026-07-19

### Uyarı kanıtı ve karar güvenliği

- Uyarı onay durumu merkezi ve açıklanabilir bir modele taşındı.
- Geçersiz eski onaylar aynı veriler için yeniden doğrulanabilir hale getirildi.
- Onaysız, değişmiş veya eski uyarı kanıtları yatırım kararını engelliyor.
- Veri kalite satırları ayrıntılı uyarı onay durumunu taşıyor.
- Uyarı listesi ve metodoloji için kararlı SHA-256 parmak izi üretildi.
- Parmak izi audit modelinde ve SQLite veritabanında saklanıyor.
- Bozulmuş kanıt veri kalite merkezinde kritik hata olarak işaretleniyor.
- Veri kalite ekranına uyarı onayı filtresi eklendi.
- Filtrelenen doğrulama listesi UTF-8 CSV olarak indirilebiliyor.

## 0.81.0 - 2026-07-19

- Onaylanan uyarılar audit geçmişine eklendi.
- Uyarı onayı güncel metodoloji ve uyarı listesiyle doğrulanmaya başlandı.
- Uyarı kanıtları şirket geçmişi ve veri kalite ekranında görünür hale getirildi.
