from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    app_name: str = "AlphaBIST AI"
    app_version: str = "0.64.0"
    scoring_methodology_version: str = "alpha-2026.2"
    technical_methodology_version: str = "technical-2026.1"

    base_dir: Path = Path(__file__).resolve().parents[2]
    data_dir: Path = base_dir / "data"
    database_path: Path = data_dir / "alphabist.db"

    default_currency: str = "TRY"
    default_market_suffix: str = ".IS"

    min_alpha_score: int = 0
    max_alpha_score: int = 100


settings = AppSettings()
