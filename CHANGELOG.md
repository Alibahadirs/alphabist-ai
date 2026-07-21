# Değişiklik günlüğü

## 1.8.0 - 2026-07-21

### Doğrulanmış gecikmeli piyasa verisi yedeği

- Son fiyat, önceki kapanış, tutar değişimi ve yüzde değişimi tek bir matematiksel doğrulama katmanında tutarlı hale getirildi.
- `borsa-api` geçmiş çıktısını güvenli sembol kontrolü, zaman aşımı ve kapanış satırı doğrulamasıyla okuyan isteğe bağlı adaptör eklendi.
- Yahoo Finance doğrudan fiyat isteği başarısız olduğunda `borsa-api` gecikmeli veri yedeği devreye alındı.
- İki sağlayıcının da başarısız olması halinde kaynakları ayrı ayrı açıklayan birleşik hata mesajı eklendi.
- Piyasa görünümünde verinin gecikmeli, resmi olmayan ve birincil/yedek kaynaktan geldiği açıkça gösterildi.
- Sağlayıcı değişim yüzdesi tutarsızsa oran son fiyat ve önceki kapanıştan yeniden hesaplanarak kullanıcıya bildirildi.

## 1.7.0 - 2026-07-21

### Rapor trendi inceleme iş akışı

- Her şirket trendi için kararlı görev kimliği ve güncel rapor/uyarı içeriğine bağlı SHA-256 sorun parmak izi eklendi.
- Açık, inceleniyor, çözüldü ve geçersiz inceleme durumları ile kullanıcı notları SQLite'ta kalıcı hale getirildi.
- Çözülmüş, geçersiz veya incelenen görevin sorun parmak izi değiştiğinde durum otomatik Yeniden açılmalı yapıldı.
- İnceleme durumu, not, yeniden açma bilgisi ve sorun parmak izi filtrelenmiş CSV raporuna eklendi.
- Rapor Trendleri ekranına yeniden açılmalı sayacı, durum filtresi ve görev durum/not güncelleme formu eklendi.
- Çözüldü veya geçersiz durumlarında açıklayıcı kullanıcı notu zorunlu hale getirildi.

## 1.6.0 - 2026-07-21

### Toplu rapor trend izleme merkezi

- SQLite rapor geçmişi her şirket için ayrı limit uygulayan tek toplu sorguyla erişilebilir hale getirildi.
- Şirketlerin son trendi, karar kilidi, uyarı seviyesi ve puan düşüşüyle 0-100 öncelik puanına dönüştürüldü.
- Kritik, uyarılı ve zayıflayan şirket sayaçlarını içeren toplu trend özeti eklendi.
- Şirket adı/kodu, önem, trend, sektör profili, minimum öncelik ve karar kilidi filtreleri eklendi.
- Filtrelenmiş trend izleme listesi UTF-8 CSV olarak dışa aktarılabilir hale getirildi.
- Sol menüye öncelik sıralı ve bozuk eski kayıtları güvenle dışlayan bağımsız Rapor Trendleri ekranı eklendi.

## 1.5.0 - 2026-07-20

### Metodoloji duyarlı rapor trendi

- Rapor çiftleri için temel, teknik ve birleşik karşılaştırılabilirlik kuralları eklendi.
- Metodoloji, sektör profili, finansal dönem ve teknik fiyat tarihi uyumsuzlukları ayrı nedenlerle raporlandı.
- Yalnız karşılaştırılabilir raporlarda Alpha, güven, teknik, birleşik ve kategori puanı değişimleri hesaplandı.
- Belirgin puan düşüşleri ve doğrulama nedeniyle kapanan yatırım kararı önem seviyeli erken uyarılara dönüştürüldü.
- Trend özeti, karşılaştırılabilirlik durumu, kategori değişimleri ve uyarılar UTF-8 CSV olarak dışa aktarılabilir hale getirildi.
- Şirket ekranına trend KPI'ları, metodoloji uyumlu geçmiş grafiği, uyarılar ve güvenli seçmeli karşılaştırma eklendi.

## 1.4.0 - 2026-07-20

### Taşınabilir ve doğrulanmış rapor geçmişi

- Şirket raporu geçmişi için sürümlü, UTF-8 JSON aktarım paketi modeli eklendi.
- Paketin genel içeriği oluşturulma saatinden bağımsız SHA-256 özetiyle korundu.
- İçe aktarmada JSON şeması, şirket kodu, rapor sayısı, her raporun kimliği ve paket bütünlüğü doğrulandı.
- Geçersiz veya farklı şirkete ait paketlerin SQLite geçmişine yazılması engellendi.
- Yeni ve yinelenen raporları ayrı sayan güvenli içe aktarma servisi eklendi.
- Şirket ekranına rapor geçmişi indirme, paket yükleme ve geçmişten seçilen iki raporu karşılaştırma eklendi.

## 1.3.0 - 2026-07-20

### Doğrulanmış şirket raporu geçmişi

- Standart analiz raporlarına oluşturulma saatinden bağımsız SHA-256 içerik parmak izi eklendi.
- Rapor anlık görüntüleri SQLite'ta şirket ve içerik kimliğine göre yinelenmeden saklandı.
- Kaydedilen raporun parmak izi veritabanına yazılmadan önce yeniden doğrulandı.
- İki raporun puan, karar, dönem, kategori ve metodoloji değişimlerini karşılaştıran motor eklendi.
- Şirket detay ekranına rapor kaydetme, geçmiş tablosu ve son iki doğrulanmış raporu karşılaştırma görünümü eklendi.

## 1.2.0 - 2026-07-20

### Standart şirket analiz raporu

- Şirket kimliği, sektör, dönem, temel puan, güven, teknik görünüm ve metodolojileri birleştiren rapor modeli eklendi.
- Birleşik puan yalnız finansal karar kapısı ve güncel teknik kalite kaydı birlikte doğrulandığında üretildi.
- Mevcut sektör analiz motorundan güçlü yönler, riskler, göstergeler ve veri kalite notları rapora taşındı.
- Yüzde, oran, puan ve tarihleri alan türüne göre biçimleyen UTF-8 Markdown rapor üreticisi eklendi.
- Genel bakış ekranına standart rapor özeti, önizleme ve tek tık Markdown indirme eklendi.

## 1.1.0 - 2026-07-20

### Görev olay denetimi

- Açık, devam eden, kapalı ve sistem kaynaklı görev durumları için güvenli geçiş kuralları eklendi.
- Her gerçek görev değişikliği önceki/yeni durum, not, sorun parmak izi ve zamanla SQLite olay geçmişine yazıldı.
- Aynı içerik tekrar kaydedildiğinde yinelenen olay oluşturulması engellendi.
- Görev olayları önceki olay özetini taşıyan SHA-256 zinciriyle bağlandı ve müdahale kontrolü eklendi.
- Veri kalite ekranına zincir sağlık durumu, kayıt kilidi, görev zaman çizelgesi ve olay CSV indirme eklendi.

## 1.0.0 - 2026-07-20

### Düzeltme görevi kanıt güvenliği

- Her düzeltme görevi için sektör, görev türü, işlem ve engellerden SHA-256 sorun parmak izi üretildi.
- Devam eden, tamamlanan veya geçersiz görevin dayanağı değiştiğinde durum otomatik `Yeniden açılmalı` yapıldı.
- Sorun parmak izi SQLite görev durumuna eklendi ve eski veritabanları için otomatik migrasyon yazıldı.
- Yeniden açılmalı görev sayacı, filtre durumu, tablo uyarısı ve güncel kanıtla yeniden kaydetme akışı eklendi.
- CSV ve görev geçmişi görünümüne sorun kanıtı ile parmak izi bilgileri eklendi.

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
