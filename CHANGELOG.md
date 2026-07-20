# Değişiklik günlüğü

## 0.99.0 - 2026-07-20

### Düzeltme görevi yaşam döngüsü

- Şirket ve görev türüne bağlı kararlı düzeltme görevi kimliği eklendi.
- Görevler için açık, devam ediyor, tamamlandı ve geçersiz durumları tanımlandı.
- Görev durumu, çalışma notu ve güncelleme zamanı SQLite veritabanında kalıcı hale getirildi.
- Veri kalite ekranına görev durumu ve not güncelleme formu eklendi.
- Durum sayaçları, durum filtresi, görev geçmişi ve yaşam döngüsü bilgili CSV raporu eklendi.

## 0.98.0 - 2026-07-20

### Sektör duyarlı düzeltme kuyruğu

- Karara hazırlık sorunlarına finansal ve teknik önem ağırlıklı 0-100 öncelik puanı eklendi.
- Eksik finansal veya teknik değerlendirmeler acil görev sırasında ayrıca yükseltildi.
- Banka, sigorta, GYO, finansal hizmet ve standart şirketler için ayrı doğrulama görevleri üretildi.
- Kritik veri ve hesaplama hataları düzeltme kuyruğunda önceliklendirildi.
- Veri kalite merkezine görev özetleri, öncelik/görev türü filtreleri ve UTF-8 CSV indirme eklendi.

## 0.97.0 - 2026-07-19

### Kanıt bütünlüğü ve yeniden doğrulama

- Doğrulama kanıt paketlerine kararlı SHA-256 içerik özeti eklendi.
- JSON paketlerinde şema, zorunlu alan, tarih, bütünlük ve uyarı parmak izi kontrolü eklendi.
- Veri kalite ekranından kanıt paketi yükleme ve nedenleriyle doğrulama akışı eklendi.
- Aynı şirkete ait iki geçerli kanıt paketinin kronolojik değişiklik karşılaştırması eklendi.
- Bütünlük kontrolünün kaynak doğrulaması veya dijital imza olmadığı arayüzde ve belgelerde açıklandı.

## 0.96.0 - 2026-07-19

### Doğrulama kanıt paketi

- Uyarı onay durumları için kullanıcıya uygulanabilir düzeltme eylemleri eklendi.
- Veri kalite özetine uyarı kanıtı durum sayaçları ve toplam sorun sayısı eklendi.
- Şirket, analiz, veri kalitesi, uyarılar ve parmak izlerini içeren sürümlü doğrulama kanıt paketi oluşturuldu.
- Kanıt paketleri kararlı JSON biçiminde dışa aktarılabilir hale getirildi.
- Veri kalite ekranına filtrelenmiş şirketler için JSON kanıt paketi indirme akışı eklendi.

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
