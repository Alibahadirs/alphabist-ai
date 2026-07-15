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
