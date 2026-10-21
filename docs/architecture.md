# Mimari Notları

## Veri Akışı

1. `battery_platform/simulator/pack.py` içindeki `BatteryPack`, her adımda (1 saniye) hücre bazlı voltaj/SoC/sıcaklık hesaplar; `bms_logic.py` bu veriye bakarak SoH ve termal durumu günceller. `faults.py` aktif arızaları fizik adımına etki katsayıları olarak enjekte eder.
2. `battery_platform/api/live_simulation.py`, bu simülasyonu arka planda (asyncio task olarak) sürekli çalıştırır.
3. Her adımda üretilen veri iki yere gider:
   - WebSocket üzerinden bağlı istemcilere (`ws_manager.py`) anında yayınlanır
   - Belirli aralıklarla (`DB_FLUSH_EVERY_N_STEPS`) toplu halde TimescaleDB'ye yazılır — DB işlemi `asyncio.to_thread` ile loop dışına taşınır, WebSocket yayınını bloklamaz
4. Frontend, `/ws/telemetry` üzerinden canlı veri alır; geçmiş analiz için REST endpoint'lerini kullanır.
5. ROS 2 köprüsü, WebSocket'e ayrı bir istemci olarak bağlanır ve `sensor_msgs/BatteryState` + `diagnostic_msgs/DiagnosticArray` yayınlar.

## Arıza Enjeksiyonu Mimarisi

Arızalar saf veri (`FaultSpec`) olarak tutulur, fiziği uygulayan taraf `FaultInjector`'dır. Bu ayrım sayesinde:
- API'den JSON olarak seri/deserialize edilebilir
- BatteryPack'ten bağımsız test edilebilir (bkz. `tests/test_faults.py`)
- Birden fazla arıza aynı anda aktif olabilir, etkileri çarpımsal/toplamsal olarak birleşir

Her `Cell.step()` çağrısına bir `CellDerating` nesnesi geçirilir: direnç çarpanı, soğutma çarpanı, kaçak akım. Arıza yokken nötr değerlerdir ve fizik birebir aynı çalışır.

Sensör kopması (`sensor_dropout`) fiziği değiştirmez — BatteryPack içindeki `_seconds_since_last_reading` sayacını artırır; bu sayaç `ThermalProtection.SENSOR_TIMEOUT_SECONDS`'ı aştığında fail-safe SHUTDOWN tetiklenir. SHUTDOWN kalıcıdır; çıkış yalnızca `POST /sim/reset-thermal` ile olur.

## Neden Ayrı Bir `bms_logic.py` Modülü?

`ThermalProtection` ve `SoHEstimator` sınıfları kasıtlı olarak `BatteryPack`'ten bağımsız, saf mantık (pure logic) olarak yazıldı. Bu sayede:
- Veritabanı veya API'ye bağımlı olmadan izole test edilebiliyor (bkz. `tests/test_bms_logic.py`)
- İleride farklı bir pack modeline (örneğin gerçek donanımdan gelen veriye) kolayca bağlanabilir

## Termal State Machine Tasarımı

Basit bir eşik kontrolü yerine histerezisli bir state machine kullanıldı:
- Sıcaklık eşik civarında küçük dalgalanmalar gösterebilir
- Giriş ve çıkış eşiklerini farklı tutarak (örn. 35°C'de uyarıya gir, 32°C'ye düşmeden çıkma) flapping önlenir
- SHUTDOWN kalıcıdır (otomatik çıkış yok) — gerçek bir BMS'te güvenlik açısından zorunlu

## Olay Kaydı (Event Log)

Eskiden termal durum yalnızca `pack_reading` satırındaki anlık bir kolondu; SHUTDOWN'a girip çıkıldığında geriye dönük hiçbir iz kalmıyordu. `event` tablosu (hypertable) "ne zaman ne oldu" sorusunu cevaplanabilir kılar: termal geçişler, arıza enjeksiyonları, profil değişiklikleri.

## Veritabanı Bağlantı Havuzu

Önceki sürüm her sorgu için `psycopg2.connect()` çağırıp bağlantıyı kapatıyordu. Artık `psycopg[pool]` (psycopg3) ile havuz kullanılıyor. Havuz ilk erişimde tembel açılır — veritabanı olmayan ortamda (CI testleri) simülatörü import etmek hata vermez.

## K-Means Doğrulaması — Dürüst Değerlendirme

Model, simülatörün kendi profil üreticisinden çıkan sentetik veriyle eğitilip yine aynı üreticiyle test ediliyor. Silhouette 0.93 ve %100 purity, modelin iyi olduğunu değil **problemin trivial olduğunu** gösterir — üç ayrık parametre setinden çıkan üç küme zaten doğal olarak ayrılır. Gerçek bir değerlendirme için bağımsız veri kaynağı veya gürültülü/karışık profiller gerekir. Bu sınırlama bilinçli olarak kabul edilmiştir; amaç gerçek dünya doğruluğu iddia etmek değil, K-Means pipeline'ının uçtan uca çalıştığını göstermektir.
