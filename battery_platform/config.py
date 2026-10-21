"""
Ortam değişkenlerinden okunan merkezi yapılandırma.

Önceki sürümde `DATABASE_URL` yokluğu modül import edilirken RuntimeError
fırlatıyordu; bu, veritabanı olmayan bir ortamda (örn. CI'da birim testleri)
simülatörü veya ML modülünü import etmeyi bile imkansız kılıyordu. Artık
kontrol, bağlantı gerçekten istendiği anda yapılıyor.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Eksik veya geçersiz yapılandırma."""


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} sayısal bir değer olmalı, '{raw}' verildi.") from exc


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, default))


@dataclass(frozen=True)
class Settings:
    """Uygulama ayarları. Varsayılanlar yerel geliştirme içindir."""

    database_url: str | None
    db_pool_min_size: int
    db_pool_max_size: int

    # Canlı simülasyon
    default_pack_id: str
    default_cell_count: int
    default_driving_style: str
    sim_dt_seconds: float
    db_flush_every_n_steps: int

    @property
    def required_database_url(self) -> str:
        """DATABASE_URL'i döner; tanımlı değilse açıklayıcı hata verir."""
        if not self.database_url:
            raise ConfigError(
                "DATABASE_URL ortam değişkeni bulunamadı. Proje kök klasöründe "
                ".env.example dosyasını .env olarak kopyalayıp "
                "DATABASE_URL=postgresql://... satırını doldurun."
            )
        return self.database_url


def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL"),
        db_pool_min_size=_env_int("DB_POOL_MIN_SIZE", 1),
        db_pool_max_size=_env_int("DB_POOL_MAX_SIZE", 8),
        default_pack_id=os.getenv("DEFAULT_PACK_ID", "PACK-1"),
        default_cell_count=_env_int("DEFAULT_CELL_COUNT", 8),
        default_driving_style=os.getenv("DEFAULT_DRIVING_STYLE", "normal"),
        sim_dt_seconds=_env_float("SIM_DT_SECONDS", 1.0),
        db_flush_every_n_steps=_env_int("DB_FLUSH_EVERY_N_STEPS", 5),
    )


settings = load_settings()
