# AlphaBIST AI Kullanım Rehberi

Bu rehber, AlphaBIST AI uygulamasını günlük kullanımda güvenli ve kolay biçimde
çalıştırmak için hazırlanmıştır.

## 1. Uygulamayı açma

Masaüstündeki **AlphaBIST AI** kısayoluna çift tıklayın. PowerShell penceresini
uygulamayı kullandığınız sürece kapatmayın. Tarayıcı otomatik açılmazsa
`http://localhost:8501` adresine gidin.

Uygulamayı kapatmak için PowerShell penceresinde `Ctrl + C` tuşlarına basın.

## 2. Finansal raporla analiz oluşturma

1. KAP'tan şirketin güncel finansal rapor PDF'sini indirin.
2. Sol menüden **PDF analizi** ekranını açın.
3. PDF'yi **Finansal rapor** alanına yükleyin.
4. Varsa aynı döneme ait faaliyet raporunu ikinci alana yükleyin.
5. Hisse kodu, şirket adı ve rapor döneminin doğru olduğunu kontrol edin.
6. Otomatik bulunan finansal değerleri resmi tablolardaki rakamlarla karşılaştırın.
7. Eksik alanları yalnızca resmi rapordan doğrulayabiliyorsanız doldurun.
8. Değerleme, yönetim ve risk puanlarını güncel bilgilerle kontrol edin.
9. Doğrulama kutularını yalnızca kontrolleri gerçekten yaptıktan sonra işaretleyin.
10. **Kontrol et ve kaydet** düğmesine basın.

## 3. Özellikle kontrol edilmesi gereken alanlar

- Hisse kodu ve şirket unvanı
- Rapor dönem sonu
- Sunum birimi: TL, bin TL veya milyon TL
- Hasılat ve önceki dönem hasılatı
- Net dönem kârı ve önceki dönem net kârı
- Özkaynak, toplam varlık ve borçlar
- Dönen varlık ve kısa vadeli yükümlülük
- Operasyonel nakit akışı
- Sektöre özel göstergeler

Otomatik çıkarılan değerleri kontrol etmeden analiz kaydetmeyin.

## 4. Sonuçları okuma

**Genel bakış** ekranında Alpha Score, analiz güveni, teknik puan ve karar
hazırlığı birlikte gösterilir. **Doğrulama gerekli** uyarısı varsa uygulama eksik
veya güvenilirliği doğrulanmamış verilerle yatırım kararı üretmez.

Piyasa fiyatları gecikmeli olabilir. Tarihsel piyasa verisi bulunamazsa son fiyat
gösterilebilir ancak teknik göstergeler ve birleşik AI puanı oluşturulmaz.

## 5. Takip listesi ve portföy

- **Takip listesi** ekranında izlemek istediğiniz şirketleri ve hedef Alpha
  puanlarını kaydedebilirsiniz.
- **Portföy** ekranında lot ve maliyet bilgilerini girerek güncel değer ile
  tahmini kâr/zararı takip edebilirsiniz.
- Portföy bilgileri yalnızca bilgisayarınızdaki yerel veritabanında saklanır.

## 6. Yedek alma

1. Sol menüden **Veri yedekleme** ekranını açın.
2. Sistem durumunun **Hazır** olduğunu kontrol edin.
3. **Yerel yedek al** düğmesine basın.
4. Bilgisayarlar arasında taşıma için **Taşınabilir paketi indir** seçeneğini
   kullanın.
5. Önemli bir geri yükleme öncesinde kurtarma tatbikatını çalıştırın.

Uygulama günlük otomatik yedek de oluşturur; yine de önemli analizlerden sonra
manuel yedek almak iyi bir alışkanlıktır.

## 7. Sık karşılaşılan durumlar

### Tarihsel fiyat verisi bulunamadı

Veri sağlayıcısı geçici olarak tarihsel veri vermiyor olabilir. Son fiyat görünse
bile teknik analiz güvenli biçimde durdurulur. Daha sonra tekrar deneyin.

### PDF'den az sayıda alan bulundu

PDF taranmış görüntü olabilir veya tablo biçimi farklı olabilir. Alanları resmi
rapordan elle doğrulayın; emin olmadığınız değeri girmeyin.

### Uygulama açılmıyor

Masaüstü kısayolunu yeniden çalıştırın. PowerShell penceresindeki ilk hata
mesajını not edin. Uygulama adresi `http://localhost:8501` şeklindedir.

## 8. Önemli uyarı

AlphaBIST AI yatırım tavsiyesi üretmez. Uygulama, kullanıcı tarafından
doğrulanan finansal verileri düzenleyen ve karar desteği sunan yerel bir analiz
aracıdır.
