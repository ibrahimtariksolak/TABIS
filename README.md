# TABIS — Tactical Battery Intelligence System

**Defense-grade battery telemetry with fault injection, thermal protection, SoH estimation & ML-driven usage analytics for unmanned ground vehicles.**

**Savunma sistemleri ve İKA (İnsansız Kara Aracı) uygulamaları için uçtan uca batarya telemetrisi, arıza enjeksiyonu, SoH kestirimi ve ML destekli kullanım analizi platformu.**

## Proje Nedir?

Bir batarya/İKA sisteminin voltaj, akım, sıcaklık ve şarj durumu (SoC) verilerini fizik tabanlı simüle eden, BMS (Battery Management System) mantığı (SoH tahmini, hücre dengeleme, termal koruma, arıza tespiti) uygulayan, K-Means ile sürüş karakteri analizi yapan ve sonucu canlı bir web dashboard'unda gösteren uçtan uca bir sistemdir.

**Arıza enjeksiyonu (fault injection)** sayesinde soğutma arızası, hücre kısa devresi, iç direnç artışı, sensör kopması gibi gerçek arıza modları runtime'da tetiklenebilir ve dashboard üzerinden gözlemlenebilir.

**ROS 2 köprüsü** ile telemetri verisi `sensor_msgs/BatteryState` ve `diagnostic_msgs/DiagnosticArray` olarak ROS 2 ekosistemine aktarılır.

## Sistem Mimarisi

```
Batarya Simülatörü (Python)
        │  (voltaj, akım, sıcaklık, SoC — fizik tabanlı)
        │  + Arıza Enjeksiyonu (FaultInjector)
        ▼
Backend API (FastAPI)  ──────────────►  TimescaleDB
        │  WebSocket (canlı akış)         (zaman serisi + olay kaydı)
        │  REST (sim kontrol, ML)
        ▼
┌───────────────────────┐
│  BMS Mantığı            │  SoH tahmini, hücre dengeleme,
│  (bms_logic.py)         │  termal koruma state machine
└───────────────────────┘
        │
        ├──► K-Means ML Modülü (sürüş karakteri)
        │
        ├──► React Dashboard (Vite + Recharts)
        │
        └──► ROS 2 Köprüsü
              sensor_msgs/BatteryState
              diagnostic_msgs/DiagnosticArray
```

## Arıza Enjeksiyonu

Simülatör beş arıza modunu destekler:

| Arıza | Seviye | Etki |
|---|---|---|
| `cooling_failure` | Paket | Soğutma durur → sıcaklık kaçar |
| `internal_resistance` | Hücre | İç direnç artar → aşırı ısınma |
| `self_discharge` | Hücre | Kaçak akım → hücre dengesizliği |
| `cell_short` | Hücre | Kısa devre → hızlı ısınma + boşalma |
| `sensor_dropout` | Paket | Sensör kopması → fail-safe SHUTDOWN |

```bash
# Soğutma arızası enjekte et
curl -X POST http://localhost:8000/sim/fault \
  -H 'Content-Type: application/json' \
  -d '{"fault_type": "cooling_failure", "severity": 0.8}'

# Hücre 0'da iç direnç artışı
curl -X POST http://localhost:8000/sim/fault \
  -H 'Content-Type: application/json' \
  -d '{"fault_type": "internal_resistance", "severity": 0.6, "cell_index": 0}'

# Sürüş profilini agresife çevir
curl -X POST http://localhost:8000/sim/profile \
  -H 'Content-Type: application/json' \
  -d '{"driving_style": "aggressive"}'

# Tüm arızaları temizle
curl -X DELETE http://localhost:8000/sim/fault
```

## Teknoloji Yığını

| Katman | Teknoloji | Gerekçe |
|---|---|---|
| Simülatör | Python (saf, bağımlılıksız) | Fizik motoru bağımsız test edilebilir olsun diye harici kütüphaneye ihtiyaç duymaz |
| Backend API | FastAPI + Uvicorn | Async destek, otomatik OpenAPI dokümantasyonu, WebSocket desteği |
| Gerçek zamanlı | WebSocket | Polling'e göre daha düşük gecikme |
| Veritabanı | PostgreSQL + TimescaleDB | Zaman serisi verisi için optimize hypertable yapısı |
| BMS Mantığı | Python (histerezisli state machine) | Termal salınım (flapping) olmadan güvenilir durum geçişleri |
| ML | scikit-learn (K-Means) | Hızlı, yorumlanabilir, düşük kaynak maliyeti |
| Frontend | React (Vite) + Recharts | Canlı grafik çizimi, component tabanlı yapı |
| ROS 2 | rclpy (Humble) | BatteryState + DiagnosticArray yayını, Nav2 entegrasyonu |
| Altyapı | Docker Compose | Tek komutla ayağa kalkan yığın (DB + backend + frontend) |
| CI | GitHub Actions | Python 3.10/3.11/3.12 üzerinde lint + test |

## Klasör Yapısı

```
battery_platform/           # Ana Python paketi
├── simulator/
│   ├── pack.py             # BatteryPack + Cell fiziği
│   ├── bms_logic.py        # ThermalProtection + SoHEstimator
│   ├── driving_profile.py  # Sürüş profili üreteci
│   └── faults.py           # Arıza enjeksiyonu
├── api/
│   ├── app.py              # FastAPI uygulaması
│   ├── schemas.py          # Pydantic şemaları
│   ├── live_simulation.py  # Arka plan simülasyonu
│   ├── simulation_state.py # Paylaşılan sim durumu
│   ├── ws_manager.py       # WebSocket yöneticisi
│   └── routes/             # telemetry, bms, ml, simulation, events
├── db/
│   ├── connection.py       # psycopg3 connection pool
│   ├── reader.py           # Sorgu katmanı
│   ├── writer.py           # Toplu INSERT
│   └── sql/                # Şema ve migrasyonlar
├── ml/
│   ├── features.py         # Özellik çıkarımı
│   ├── predict.py          # Tahmin + öneri
│   └── train_model.py      # Model eğitimi
└── config.py               # Merkezi yapılandırma

ros2_bridge/                # ROS 2 ament_python paketi
├── ros2_bridge/
│   └── battery_bridge_node.py
├── launch/
├── config/
└── package.xml

frontend/                   # React (Vite) dashboard
tests/                      # pytest test paketi (33 test)
```

## Kurulum

**Gereksinimler:** Python ≥ 3.10, Docker, Node.js 18+ (frontend için)

### Tek komutla (Docker Compose)

```bash
git clone https://github.com/ibrahimtariksolak/battery-health-platform.git
cd battery-health-platform
cp .env.example .env    # gerekirse şifreleri düzenle
docker compose up -d
```

- Dashboard: `http://localhost:3000`
- API / Swagger: `http://localhost:8000/docs`

### Yerel geliştirme

```bash
# 1) Veritabanı
docker compose up -d db

# 2) Python
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows
pip install -e ".[dev]"

# 3) Şemayı uygula (ilk seferde)
cat battery_platform/db/sql/schema.sql | docker exec -i battery-db psql -U battery_admin -d battery_health
cat battery_platform/db/sql/migration_faz5.sql | docker exec -i battery-db psql -U battery_admin -d battery_health

# 4) ML modelini eğit (bir kereye mahsus)
python -m battery_platform.ml.train_model

# 5) Backend
uvicorn battery_platform.api.app:app --reload

# 6) Frontend (yeni terminal)
cd frontend && npm install && npm run dev
```

### ROS 2 köprüsü (opsiyonel)

```bash
source /opt/ros/humble/setup.bash
cd ros2_bridge
colcon build --packages-select battery_ros2_bridge
source install/setup.bash
ros2 launch battery_ros2_bridge bridge.launch.py
```

Yayınlanan topic'ler:
- `/battery_state` (`sensor_msgs/BatteryState`)
- `/diagnostics` (`diagnostic_msgs/DiagnosticArray`)

## Testler

```bash
pip install -e ".[dev]"
pytest tests/ -v          # 33 test
ruff check battery_platform/ tests/
```

CI, her push ve PR'da Python 3.10, 3.11, 3.12 üzerinde otomatik çalışır.

## API Endpoint'leri

| Yol | Yöntem | Açıklama |
|---|---|---|
| `/healthz` | GET | Sağlık kontrolü |
| `/telemetry/latest` | GET | Son pack okuması |
| `/telemetry/history` | GET | Geçmiş okumalar |
| `/bms/status` | GET | BMS durumu + hücre detayı |
| `/ml/driving-style` | GET | Sürüş karakteri analizi |
| `/sim/state` | GET | Simülasyon durumu |
| `/sim/fault` | POST | Arıza enjekte et |
| `/sim/fault` | DELETE | Arızaları temizle |
| `/sim/profile` | POST | Sürüş profilini değiştir |
| `/sim/reset-thermal` | POST | SHUTDOWN'dan çık |
| `/events/` | GET | Olay kayıtları |
| `/ws/telemetry` | WS | Canlı veri akışı |

## Bilinen Sınırlamalar

- K-Means doğrulaması daireseldir: model, simülatörün kendi profil üreticisinden çıkan veriyle eğitilip yine aynı üreticiyle test ediliyor. Silhouette 0.93 ve %100 purity, modelin değil problemin trivial olduğunu gösterir. Gerçek bir değerlendirme için bağımsız veri kaynağı gerekir.
- Hücreler arası termal etkileşim modellenmiyor (her hücrenin sıcaklığı bağımsız).
- SoC tahmini saf coulomb counting'e dayanıyor; EKF/UKF tabanlı kestirim gelecek çalışma.
- Frontend henüz arıza enjeksiyonu butonlarını içermiyor — API üzerinden `curl` ile kullanılır.

## Lisans

MIT
