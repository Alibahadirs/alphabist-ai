# AlphaBIST AI

Borsa İstanbul şirketlerini finansal kalite, büyüme, borçluluk, likidite,
nakit akışı, verimlilik, değerleme, risk ve yönetim kriterleriyle puanlayan
yerel Streamlit uygulaması.

## Özellikler

- Finansal rapor ve faaliyet raporu PDF'lerinden otomatik veri çıkarma
- Parasal tutar, yüzde ve puan alanlarını ayıran PDF veri sözleşmesi
- Banka, sigorta, GYO ve sanayi raporlarına göre sektör alanı filtreleme
- Şirket kodu, unvan ve rapor dönemini birlikte doğrulayan kayıt güvenlik kapısı
- Kullanıcı doğrulamasından sonra Alpha Score hesaplama
- Alan türüne uygun TL, yüzde, oran ve puan biçimleri
- Gecikmeli piyasa verileri ve teknik analiz göstergeleri
- Yahoo Finance kesintilerinde isteğe bağlı `borsa-api` gecikmeli fiyat yedeği
- Sağlayıcı yüzdesi yerine kapanış fiyatlarından doğrulanan günlük değişim
- Yahoo Finance ve `borsa-api` için kaynak uygunluk politikası
- Fiyat, tarih ve günlük değişimi karşılaştıran piyasa veri kontrolü ekranı
- Piyasa kontrolleri için SHA-256 korumalı ve yinelenmeyen SQLite geçmişi
- Çapraz doğrulama oranı, ardışık sorunlar ve CSV kontrol geçmişi
- En fazla 20 kayıtlı şirket için kullanıcı kontrollü toplu piyasa denetimi
- Sorunlu piyasa kayıtları için öncelikli düzeltme iş listesi
- Sağlık durumu, önem, öncelik ve metin tabanlı görev filtreleri
- Görev kimliği ve sorun parmak izi içeren Excel uyumlu CSV kanıt raporu
- Piyasa görevleri için kalıcı durum, çalışma notu ve yeniden açma uyarısı
- SHA-256 bağlantılı piyasa görevi olay geçmişi ve zaman çizelgesi
- İş akışı durumunu taşıyan genişletilmiş düzeltme kuyruğu raporu
- Son kaydı eski, kısmi, eksik veya bütünlüğü bozuk şirketleri önceleyen sağlık özeti
- Tek transaction ile yinelenmeyen toplu piyasa geçmişi ve UTF-8 sağlık CSV'si
- Her toplu kontrol için sayaç ve hisse sonucu tutarlılığı doğrulanan çalışma kaydı
- Çalışma özeti ile piyasa anlık görüntülerini atomik ve parmak izi korumalı saklama
- Toplu çalışma geçmişi, son çalışma ayrıntısı ve kanıt bilgili UTF-8 CSV çıktısı
- Bozuk JSON, şema ve parmak izi sorunlarını kayıt bazında ayıran dayanıklı geçmiş denetimi
- Son/ortalama doğrulama oranı ve ardışık sorunlu çalışma sağlık göstergeleri
- Geçersiz kayıtları gizlemeden filtreleyen ve CSV'ye taşıyan toplu geçmiş görünümü
- Kaynak politikası, güncellik ve fiyat-grafik uyumunu birleştiren merkezi karar kapısı
- Teknik puan, karşılaştırma, takip listesi ve portföyde ortak piyasa veri denetimi
- Temel ve teknik puanı birleştiren AI puanı
- Şirket karşılaştırma ve takip listesi
- Finansal ölçütlerle çalışan şirket tarayıcı ve otomatik sıralama
- Lot, maliyet, güncel değer ve kâr/zarar hesaplayan portföy ekranı
- Alpha Score geçmişi ve önceki analize göre puan değişimi
- PDF, faaliyet raporu, manuel giriş ve kullanıcı düzeltmesi için veri kaynağı geçmişi
- Her finansal göstergenin kaynağını alan bazında izleme
- Banka, sigorta, GYO ve finansal hizmet şirketleri için sektöre özgü doğrulama
- Sektör puanlaması ile zorunlu göstergeleri birebir eşleştiren tamlık kontrolü
- Finansal hizmetlerde sermaye yeterliliği veya borç / özkaynak alternatifi
- Puan tablolarında sektöre özgü kategori adı ve hesap dayanağı
- Ham kategori toplamı, veri yeterliliği katsayısı ve nihai puan düzeltme izi
- Değerleme, yönetim ve risk puanlarında kayıt öncesi zorunlu kullanıcı doğrulaması
- Veri yeterliliği ve kaynak kanıtına göre bağımsız analiz güveni puanı
- Düşük güvenli kayıtlarda yatırım kararını otomatik doğrulama seviyesine çekme
- Her analiz için metodoloji, kategori puanları, güven ve karar anlık görüntüsü
- Son iki analiz arasında toplam puan, güven ve kategori değişimi karşılaştırması
- Tam rapor dönem sonu, güncellik ve finansal/faaliyet raporu dönem uyumu kontrolü
- Veri kalite merkezinde toplu rapor güncelliği özeti, yaşı ve durum filtresi
- Metodolojiye duyarlı analiz parmak izi ve yinelenen kayıt engelleme
- Kaynak PDF'ler için ayrı SHA-256 belge kimliği ve geçmiş doğrulaması
- Aynı PDF'nin farklı şirket veya rapor döneminde kullanılmasını engelleme
- Finansal/faaliyet raporu, hisse kodu ve şirket unvanı çapraz doğrulaması
- Finansal ve faaliyet raporu sektör profili çelişkisinde zorunlu kullanıcı doğrulaması
- TL, bin TL ve milyon TL sunum birimini yalnızca parasal kalemlere uygulama
- Büyüme sütunları için geçen yılın aynı karşılaştırma dönemi doğrulaması
- Banka, sigorta, GYO ve finansal hizmet raporlarına özgü gelir satırı eşlemesi
- ROE ve aktif devir hızında ortalama özkaynak/aktif kullanımı
- PDF'de bulunamayan finansal değerleri sıfır yerine eksik olarak koruma
- Sektöre duyarlı kaynak tutar ve bilanço tutarlılık kontrolleri
- Banka, sigorta, GYO ve finansal hizmet oranlarında makul aralık kontrolleri
- Olağan dışı doğrulama uyarılarında kayıt öncesi zorunlu kullanıcı onayı
- Onaylı uyarıları veri kalite durumu ve analiz güveninde ayrı değerlendirme
- Onaylanan veri uyarılarının denetlenebilir analiz anlık görüntüsünü saklama
- Uyarı onayını güncel metodoloji ve birebir uyarı listesiyle doğrulama
- Şirket geçmişi ve veri kalite merkezinde onaylanan uyarı kanıtını gösterme
- Uyarı onayının neden geçerli veya geçersiz olduğunu ayrıntılı durumla açıklama
- Onaysız uyarılı analizlerde güven puanı ve yatırım kararı kilidi
- Aynı finansal veriyi geçerli uyarı onayıyla yeniden audit kaydına alma
- Uyarı listesi ve metodolojiye bağlı SHA-256 kanıt parmak izi
- Eksik veya bozulmuş uyarı kanıtını otomatik yeniden doğrulamaya yönlendirme
- Bozulmuş uyarı kanıtını veri kalite merkezinde kritik hata olarak gösterme
- Veri kalite merkezinde uyarı onay durumuna göre filtreleme
- Filtrelenmiş veri kalite listesini UTF-8 CSV raporu olarak indirme
- Uyarı kanıtı durumuna göre uygulanabilir düzeltme önerileri
- Veri kalite özetinde uyarı kanıtı durum sayaçları
- Şirket bazlı, sürümlü ve makine tarafından okunabilir doğrulama kanıt paketi
- Seçilen şirketin doğrulama kanıt paketini JSON olarak indirme
- Kanıt paketlerinde içerik değişikliğini tespit eden SHA-256 bütünlük özeti
- Yüklenen kanıt JSON'unda şema, bütünlük ve uyarı kanıtı doğrulaması
- Aynı şirkete ait iki kanıt paketi arasında doğrulamalı değişiklik karşılaştırması
- Karara hazırlık sorunları için 0-100 öncelik puanı ve önem seviyesi
- Banka, sigorta, GYO, finansal hizmet ve standart şirketlere özel düzeltme görevleri
- Kritik hesap hatalarını öncelik sırasında yükselten düzeltme kuyruğu
- Öncelik ve görev türüne göre filtrelenebilir veri kalite iş listesi
- Filtrelenmiş düzeltme kuyruğunu UTF-8 CSV olarak indirme
- Düzeltme görevleri için kararlı ve tekrar üretilebilir görev kimliği
- Açık, devam ediyor, tamamlandı ve geçersiz görev yaşam döngüsü
- Görev durumu ile çalışma notlarını SQLite'ta kalıcı saklama
- Veri kalite ekranından görev durumu ve not güncelleme
- Durum sayaçları, görev geçmişi ve yaşam döngüsü bilgili CSV raporu
- Düzeltme görevinin güncel dayanağını izleyen SHA-256 sorun parmak izi
- Değişen görev dayanağında otomatik `Yeniden açılmalı` güvenlik durumu
- Eski görev kayıtları için güvenli SQLite parmak izi migrasyonu
- Sorun kanıtı durumu, parmak izi ve yeniden açma uyarısını içeren görev raporu
- Kapalı görevlerin güvenli biçimde yeniden açılmasını zorunlu kılan durum geçiş kuralları
- Her gerçek görev değişikliğini saklayan yinelenmeyen SQLite olay geçmişi
- Geçmiş müdahalesini tespit eden SHA-256 bağlantılı görev olay zinciri
- Zincir bütünlüğü bozuk görevlerde yeni kayıt engeli
- Görev zaman çizelgesi ve olay zinciri bilgilerini içeren UTF-8 CSV raporu
- Şirket, sektör, dönem, Alpha Score, güven ve teknik görünümü birleştiren standart analiz raporu
- Yalnız doğrulanmış finansal ve teknik verilerle birleşik puan/karar üretimi
- Sektör profiline göre güçlü yön, risk ve gösterge değerlendirmesi
- Yüzde, oran, puan ve tarih alanlarını türüne göre biçimleyen Markdown raporu
- Şirket detay ekranından rapor önizleme ve UTF-8 Markdown indirme
- Standart analiz raporları için zaman bilgisinden bağımsız SHA-256 içerik kimliği
- Aynı rapor içeriğinin yinelenmesini engelleyen SQLite anlık görüntü geçmişi
- Son iki doğrulanmış raporda puan, karar, dönem ve metodoloji değişimi karşılaştırması
- Rapor geçmişini sürümlü ve bütünlük kontrollü UTF-8 JSON paketi olarak dışa aktarma
- JSON paketinde şema, şirket, rapor sayısı, rapor ve paket parmak izi doğrulaması
- Doğrulanmış rapor paketini seçili şirkete yinelenmeden güvenli içe aktarma
- Geçmişten seçilen herhangi iki doğrulanmış şirket raporunu karşılaştırma
- Rapor çiftlerinde metodoloji, sektör profili ve dönem sırası karşılaştırılabilirlik kontrolü
- Yalnız karşılaştırılabilir kayıtlardan Alpha, güven, teknik ve birleşik puan trendi
- Belirgin puan düşüşleri ve karar kilidi için önem seviyeli erken uyarılar
- Güncel metodoloji ve sektör profiline göre filtrelenen Alpha Score geçmiş grafiği
- Trend özeti, karşılaştırılabilirlik notları ve uyarıları içeren UTF-8 CSV raporu
- Tüm şirketlerin son raporlarını şirket bazlı limitle tek sorguda getiren toplu geçmiş erişimi
- Karar kilidi, önem seviyesi ve puan düşüşüne göre önceliklendirilen şirket trend izleme motoru
- Şirket, önem, trend, sektör, minimum öncelik ve karar kilidi filtreleri
- Filtrelenmiş toplu trend listesini UTF-8 CSV olarak dışa aktarma
- Sol menüde kritik ve zayıflayan şirketleri gösteren bağımsız Rapor Trendleri ekranı
- Trend uyarıları için şirket bazında kararlı görev kimliği ve içeriğe duyarlı SHA-256 sorun parmak izi
- Açık, inceleniyor, çözüldü ve geçersiz trend inceleme durumlarını SQLite'ta saklama
- Kapanmış veya incelenen görevin dayanağı değiştiğinde otomatik Yeniden açılmalı durumu
- İnceleme durumu, not, yeniden açma bilgisi ve sorun kimliğini filtre ve CSV raporuna taşıma
- Rapor Trendleri ekranından seçilen şirket için kalıcı durum ve inceleme notu yönetimi
- PDF kaynak tutarlarını düzeltme ve oranları anında yeniden hesaplama
- Her analiz için ham finansal tutar anlık görüntüsü ve hesap izi
- Dönem bazlı gösterge değeri, birim ve kaynak anlık görüntüsü
- Ham tutarlardan yeniden hesaplama ve metodolojiye duyarlı tutarlılık kontrolü
- Formül uyuşmazlıklarını veri kalite merkezinde kritik kayıt olarak gösterme
- Hesap uyuşmazlığında analiz güvenini ve yatırım kararını otomatik olarak durdurma
- Liderlik, tarama ve takip hedeflerinde doğrulama temelli karara hazırlık kontrolü
- Portföyde güven ağırlıklı puan ve doğrulama gereken pozisyon payı
- Kullanıcıya özel SQLite verisini kaynak kodu commitlerinden ayırma
- SQLite yedeğini bütünlük kontrolüyle indirme ve güvenli geri yükleme
- Geri yükleme öncesi güvenlik kopyalarını listeleme ve yeniden indirme
- Python, bağımlılık, veri klasörü ve SQLite için merkezi başlangıç ön kontrolü
- Gereksinimler değişmedikçe paketleri yeniden kurmayan tek komutluk Windows başlatıcı
- Çalışan uygulamayı algılayarak ikinci Streamlit sürecini engelleme
- Veritabanı bütünlüğü, zorunlu tablolar ve gerçek yedek üretimini sınayan sistem durumu
- Portföy pozisyon ve şirket profili yoğunlaşma analizi
- Ağırlık bazlı yoğunlaşma endeksi ve etkin pozisyon sayısı
- Portföy için mekanik fiyat şoku stres senaryoları
- En büyük pozisyon ve şirket profili için yoğunlaşma stres testi
- Portföy fiyatları için kaynak, tarih ve güncellik doğrulaması
- Stres testi için değer ağırlıklı güncel fiyat kapsamı eşiği
- Genel bakış, takip listesi ve portföyde ortak fiyat güncelliği kuralı
- Son fiyat ile teknik grafik tarihi ve kapanış değeri çapraz kontrolü
- Karşılaştırmada şirket bazlı doğrulanmış teknik puan kapsamı
- Yinelenmeyen, kaynak ve metodoloji izli teknik puan geçmişi
- Takip listesinde güncel teknik puan, değişim ve güçlenme takibi
- Hisse tarayıcıda güncel teknik puan ve güçlenme filtreleri
- Kayıtlı şirketler için doğrulamalı toplu teknik puan güncellemesi
- En fazla 20 hisselik, takip listesi ve portföy öncelikli teknik güncelleme
- Portföy için doğrulama kapsamlı, değer ağırlıklı teknik ve birleşik puan
- Birleşik portföy puanını engelleyen şirket bazlı doğrulama listesi
- Veri kalite merkezinde teknik kayıt güncelliği, kaynak ve metodoloji görünümü
- Veri kalite merkezinden sorunlu teknik kayıtları doğrulamalı toplu yenileme
- Finansal ve teknik doğrulamayı birleştiren şirket bazlı karara hazırlık kuyruğu
- Hisse tarayıcıda finansal ve birleşik karara hazırlık filtreleri
- Takip listesinde finansal ve birleşik karara hazırlık görünümü
- Şirket karşılaştırmada temel lider ve doğrulanmış birleşik lider ayrımı
- Portföyde pozisyon kesişimine dayalı birleşik hazırlık ve değer kapsamı
- Teknik kayıtlarda güncellik, metodoloji, hizalama ve kaynak sağlık kontrolü
- Teknik toplam puan, kategori kırılımı ve sinyal bütünlüğü doğrulaması
- Teknik güçlenmede aynı metodolojili ve doğrulanmış geçmiş kayıt karşılaştırması
- Aynı piyasa günündeki bozuk teknik kaydı doğrulanmış veriyle yerinde onarma
- Birleşik AI puanında finansal ve teknik karara hazırlık kapısı
- Alpha Score değişiminde aynı metodoloji sürümüne ait geçmiş karşılaştırması
- Alpha Score değişiminde aynı sektör profiline ait geçmiş karşılaştırması
- SQLite ile yerel veri saklama

## İlk kurulum ve çalıştırma

PowerShell'de proje klasöründeyken:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start.ps1
```

Başlatıcı sanal ortamı yoksa oluşturur, gerekli paketleri kurar, sistem ön
kontrolünü çalıştırır ve uygulamayı tarayıcı açmadan başlatır. Sonraki
çalıştırmalarda `requirements.txt` değişmediyse paketler yeniden kurulmaz.

Uygulama zaten `8501` portunda çalışıyorsa ikinci bir süreç başlatmak yerine
mevcut adresi bildirir.

Yahoo Finance doğrudan bağlantısına ek olarak gecikmeli fiyat yedeğini
etkinleştirmek için Node.js kurulu bir sistemde:

```powershell
npm install -g borsa-api
```

Bu paket de Yahoo Finance tabanlıdır; gerçek zamanlı veya resmi BIST verisi
sağlamaz. Uygulama paketi yalnızca birincil fiyat isteği başarısız olduğunda
kullanır ve günlük değişim yüzdesini son iki kapanıştan yeniden hesaplar.

Uygulama varsayılan olarak `http://localhost:8501` adresinde açılır.

Uygulama içindeki **Veri yedekleme** ekranı; Python ve paket hazırlığını,
SQLite bütünlüğünü, kayıt sayısını, güvenlik kopyalarını ve geçerli yedek
üretilebildiğini birlikte gösterir.

## Yerel veri güvenliği

Şirket analizleri, takip listesi ve portföy kayıtları `data/alphabist.db`
dosyasında yalnızca yerel bilgisayarda tutulur. Bu dosya Git tarafından
izlenmez ve GitHub'a gönderilmez. Uygulama yeni bir kurulumda veritabanını
otomatik oluşturur.

## Testler

```powershell
python -m pytest -q
```

## Kullanım akışı

1. **Şirket ekle veya güncelle** ekranını açın.
2. Finansal raporu ve isteğe bağlı faaliyet raporunu yükleyin.
3. Otomatik bulunan şirket bilgilerini ve finansal değerleri kontrol edin.
4. Analizi kaydedin.
5. Genel bakış ekranında Alpha Score, teknik görünüm ve puan geçmişini izleyin.

## Veri notu

PDF çıkarımı hataya açık olabileceği için otomatik bulunan değerler kaydetmeden
önce resmi KAP/SPK tablolarıyla doğrulanmalıdır. Piyasa verileri gecikmeli olabilir.
Uygulama yatırım tavsiyesi üretmez; karar desteği sağlar.
Kanıt paketi bütünlük kontrolü dosyanın dışa aktarımdan sonra değişmediğini sınar;
dosyayı oluşturan kişi veya sistemin kimliğini doğrulayan dijital imza değildir.
