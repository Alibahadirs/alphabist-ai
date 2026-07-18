# AlphaBIST AI

Borsa İstanbul şirketlerini finansal kalite, büyüme, borçluluk, likidite,
nakit akışı, verimlilik, değerleme, risk ve yönetim kriterleriyle puanlayan
yerel Streamlit uygulaması.

## Özellikler

- Finansal rapor ve faaliyet raporu PDF'lerinden otomatik veri çıkarma
- Kullanıcı doğrulamasından sonra Alpha Score hesaplama
- Alan türüne uygun TL, yüzde, oran ve puan biçimleri
- Gecikmeli piyasa verileri ve teknik analiz göstergeleri
- Temel ve teknik puanı birleştiren AI puanı
- Şirket karşılaştırma ve takip listesi
- Finansal ölçütlerle çalışan şirket tarayıcı ve otomatik sıralama
- Lot, maliyet, güncel değer ve kâr/zarar hesaplayan portföy ekranı
- Alpha Score geçmişi ve önceki analize göre puan değişimi
- PDF, faaliyet raporu, manuel giriş ve kullanıcı düzeltmesi için veri kaynağı geçmişi
- Her finansal göstergenin kaynağını alan bazında izleme
- Banka, sigorta, GYO ve finansal hizmet şirketleri için sektöre özgü doğrulama
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
- TL, bin TL ve milyon TL sunum birimini yalnızca parasal kalemlere uygulama
- Büyüme sütunları için geçen yılın aynı karşılaştırma dönemi doğrulaması
- Banka, sigorta, GYO ve finansal hizmet raporlarına özgü gelir satırı eşlemesi
- ROE ve aktif devir hızında ortalama özkaynak/aktif kullanımı
- PDF'de bulunamayan finansal değerleri sıfır yerine eksik olarak koruma
- Sektöre duyarlı kaynak tutar ve bilanço tutarlılık kontrolleri
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
- SQLite ile yerel veri saklama

## Çalıştırma

PowerShell'de proje klasöründeyken:

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run main.py
```

Python komutu sistemde tanımlı değilse:

```powershell
py -m streamlit run main.py
```

Uygulama varsayılan olarak `http://localhost:8501` adresinde açılır.

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
