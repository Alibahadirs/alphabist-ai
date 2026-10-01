from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "portfoy.db"


@dataclass(frozen=True)
class Settings:
    app_name: str = "Portföy Yöneticisi"
    app_version: str = "0.1.0"

    # Öneri motorunda kullanılan gösterge pencereleri (gün).
    sma_short: int = 20
    sma_long: int = 50
    rsi_period: int = 14
    momentum_period: int = 20
    volatility_period: int = 20
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bollinger_window: int = 20
    bollinger_std: float = 2.0

    # Göstergelerin seçilen tarih aralığının başında da hesaplanabilmesi için
    # geriye doğru ek olarak çekilen ısınma verisi (gün).
    warmup_days: int = 120

    # Sinyal backtest'inde varsayılan tutma süresi (işlem günü, ~1 ay).
    backtest_default_holding_days: int = 20

    cache_ttl_seconds: int = 3600


settings = Settings()
