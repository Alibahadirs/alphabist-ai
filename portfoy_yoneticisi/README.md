# Portföy Yöneticisi

AlphaBIST AI'dan bağımsız, kişisel kullanım için ikinci bir Streamlit uygulaması.
Belirtilen tarih aralığı için BIST hisseleri, kıymetli madenler (altın/gümüş) ve
döviz kurları hakkında teknik gösterge tabanlı Al/Sat/Tut önerisi üretir ve
kişisel portföyünüzü yerel olarak izlemenizi sağlar.

Bu uygulama **yatırım tavsiyesi vermez**; yalnızca geçmiş fiyat verisinden
hesaplanan mekanik göstergelere (hareketli ortalama, RSI, momentum, volatilite)
dayalı bir karar-destek aracıdır.

## Çalıştırma

Bu klasör, proje kökündeki `.venv` sanal ortamını kullanır (aynı bağımlılıklar
zaten kurulu: `streamlit`, `pandas`, `numpy`, `yfinance`). Proje kökünden:

```powershell
.\.venv\Scripts\streamlit.exe run portfoy_yoneticisi\main.py
```

Farklı bir sanal ortam kullanmak isterseniz `portfoy_yoneticisi\requirements.txt`
dosyasını kurabilirsiniz:

```powershell
pip install -r portfoy_yoneticisi\requirements.txt
streamlit run portfoy_yoneticisi\main.py
```

Uygulama varsayılan olarak `http://localhost:8501` adresinde açılır (AlphaBIST AI
aynı anda çalışıyorsa Streamlit otomatik olarak sonraki boş portu — `8502` vb. —
kullanır).

## Ekranlar

- **Öneri Tarama** — Seçtiğiniz enstrüman listesi (BIST hisseleri dahil ~720
  enstrümanlık tam katalog, altın/gümüş, döviz) ve tarih aralığı için toplu
  Al/Sat/Tut önerisi, aralık getirisi, volatilite ve RSI tablosu. Tüm
  enstrümanlar tek bir toplu yfinance isteğiyle çekilir (ortak ticker'lar
  tekilleştirilir). Sonuç tablosu CSV/Excel olarak indirilebilir.
- **Detaylı Analiz** — Tek bir enstrüman için fiyat/SMA/Bollinger grafiği, RSI
  ve MACD grafikleri, öneri skorunun faktör bazlı dökümü, aralık performans
  detayları (toplam getiri, volatilite, maksimum düşüş, en iyi/kötü gün) ve
  **sinyal backtest'i**: geçmişte üretilmiş olacak her Al/Sat sinyalinin,
  seçtiğiniz tutma süresi sonrasında gerçekten doğru yönde hareket edip
  etmediğini (isabet oranı, ortalama ileri getiri) gösterir. Backtest
  lookahead-bias içermez — her günün sinyali yalnızca o güne kadarki veriyle
  hesaplanır.
- **Portföyüm** — Kendi pozisyonlarınızı (enstrüman, miktar, maliyet, alış
  tarihi) ekleyip; güncel fiyat, güncel değer, kâr/zarar yüzdesi, güncel öneri
  ve **varlık sınıfı / enstrüman bazlı dağılım grafikleriyle** birlikte
  izleyin. Pozisyon tablosu CSV/Excel olarak indirilebilir. Veriler yalnızca
  bu bilgisayarda `portfoy_yoneticisi/data/portfoy.db` dosyasında tutulur ve
  Git tarafından izlenmez.

## Öneri motoru nasıl çalışır

Her enstrüman için beş ağırlıklı faktörden -1 ile +1 arasında bir toplam skor
hesaplanır:

- **Trend (%35)** — 20 günlük ve 50 günlük hareketli ortalamaların farkı.
- **MACD (%15)** — 12/26/9 MACD histogramı, log-fiyat üzerinden (yüzdesel
  trendlerde işaret bozulmasın diye); trend ivmesini ölçer.
- **RSI (%20)** — 14 günlük RSI; 30 altı aşırı satım (alım yönlü), 70 üstü aşırı
  alım (satım yönlü) olarak puanlanır.
- **Momentum (%20)** — Son 20 günlük yüzde getiri.
- **Bollinger %B (%10)** — Fiyatın 20 günlük, 2 standart sapmalı bant
  içindeki konumu; alt banda yakınlık alım, üst banda yakınlık satım yönlü
  yorumlanır.

Toplam skor ≥ **+0.25** ise **Al**, ≤ **-0.25** ise **Sat**, aksi halde **Tut**
önerisi üretilir. Yıllıklandırılmış volatilite doğrudan skora girmez; yüksek
volatilitede (>%45) güven seviyesi düşürülür. Göstergelerin sağlıklı
hesaplanabilmesi için seçilen başlangıç tarihinden önce ek olarak ~120 günlük
"ısınma" verisi çekilir; ekranlarda yalnızca seçtiğiniz aralık gösterilir.

## Günlük e-posta uyarısı (opsiyonel)

Portföyünüzdeki (ve isteğe bağlı ek izleme listesindeki) enstrümanları her gün
tarayıp Al/Sat sinyaline ulaşanları e-postayla bildiren bir arka plan görevi
kurabilirsiniz (AlphaBIST AI'daki günlük rapor özelliğiyle aynı desen).
**Bu kurulum gerçek bir Gmail uygulama parolası istediği ve bilgisayarınızda
kalıcı bir zamanlanmış görev oluşturduğu için sizin kendiniz çalıştırmanız
gerekir:**

```powershell
cd portfoy_yoneticisi
..\.venv\Scripts\python.exe configure_daily_alert.py
powershell -ExecutionPolicy Bypass -File .\install_daily_alert_task.ps1
```

Parola projeye veya GitHub'a yazılmaz; Windows kimlik kasasında saklanır.
Görev her gün 19:30'da çalışır; hafta sonları BIST kapalı olduğu için otomatik
atlanır. Kurulumdan sonra e-posta göndermeden test etmek için:

```powershell
..\.venv\Scripts\python.exe -m pm.alerts.runner --dry-run --force
```

## Toplu veri çekimi

Öneri Tarama ve Portföyüm ekranları, seçilen tüm enstrümanlar için ayrı ayrı
istek atmak yerine **tek bir** yfinance toplu indirme çağrısı yapar; aynı
ticker'ı paylaşan enstrümanlar (ör. ons altın ve gram altının ortak kullandığı
USD/TRY kuru) yalnızca bir kez indirilir. Bu sayede onlarca enstrümanlık bir
tarama bile saniyeler içinde tamamlanır.

## Varlık kataloğu

- **Hisse (BIST)** — Seçim listesi, KAP'ın BIST şirket sayfası taranarak elde
  edilen ~700 hisselik tam listeyi içerir (24 saat önbelleklenir; ağ
  erişilemezse küçük bir varsayılan listeye düşülür). THYAO, GARAN, ASELS,
  SISE, KCHOL, EREGL gibi birkaç likit hisse varsayılan olarak önceden seçili
  gelir. Ayrıca herhangi bir BIST kodunu serbestçe girebilirsiniz (`.IS`
  uzantısı otomatik eklenir).
- **Kıymetli Maden** — Ons altın/gümüş (USD) ve TL bazında gram altın/gümüş
  (ons fiyatı × USD/TRY kuru ile hesaplanır).
- **Döviz** — USD/TRY, EUR/TRY, GBP/TRY, EUR/USD.

Veriler [Yahoo Finance](https://finance.yahoo.com) üzerinden `yfinance` ile
gecikmeli olarak çekilir; resmi bir veri kaynağı değildir.

## Testler

```powershell
cd portfoy_yoneticisi
..\.venv\Scripts\python.exe -m pytest -q
```

Testler ağ bağlantısı gerektirmez; göstergeler ve öneri motoru sentetik fiyat
serileriyle doğrulanır.
