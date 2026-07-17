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
