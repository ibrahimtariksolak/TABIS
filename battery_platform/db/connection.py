"""
TimescaleDB bağlantısını yöneten merkezi modül.

Önceki sürüm her sorgu için `psycopg2.connect()` çağırıp bağlantıyı kapatıyordu.
Saniyede bir yazan bir telemetri hattında bu, her beş saniyede yeni bir TCP
bağlantısı + kimlik doğrulama turu demekti. Artık bir bağlantı havuzu (pool)
kullanılıyor ve havuz ilk kullanımda tembel (lazy) açılıyor - böylece
veritabanı olmayan bir ortamda modülü import etmek hata vermiyor.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

from psycopg import Connection
from psycopg_pool import ConnectionPool

from battery_platform.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Havuzu döner, gerekiyorsa açar. Süreç başına tek havuz tutulur."""
    global _pool
    if _pool is None:
        logger.info("Veritabanı bağlantı havuzu açılıyor (max_size=%s)", settings.db_pool_max_size)
        _pool = ConnectionPool(
            conninfo=settings.required_database_url,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            open=True,
            # Havuz kapalıysa sonsuza kadar beklemek yerine makul sürede hata ver;
            # aksi halde bir endpoint sessizce takılır.
            timeout=10.0,
        )
    return _pool


def close_pool():
    """Uygulama kapanırken havuzu düzgünce kapatır."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
        logger.info("Veritabanı bağlantı havuzu kapatıldı.")


@contextmanager
def get_connection() -> Iterator[Connection]:
    """
    Havuzdan bir bağlantı ödünç alır ve blok bitince geri verir.

    Dikkat: bu artık bir context manager - eski `conn = get_connection()`
    kullanımı yerine `with get_connection() as conn:` yazılmalı. Bağlantı
    kapatılmaz, havuza döner; hata durumunda psycopg otomatik rollback yapar.
    """
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


async def run_db(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    Senkron bir veritabanı fonksiyonunu worker thread'de çalıştırır.

    psycopg'nin senkron arayüzü asyncio event loop'unu bloklar; canlı
    simülasyon saniyede bir WebSocket yayını yaptığı için toplu INSERT'in
    loop'u durdurması doğrudan yayın gecikmesi (jitter) olarak görünüyordu.
    Bu sarmalayıcı, DB işini loop'un dışına taşır.
    """
    return await asyncio.to_thread(func, *args, **kwargs)
