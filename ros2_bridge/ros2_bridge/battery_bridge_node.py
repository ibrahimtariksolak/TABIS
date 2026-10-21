"""
Batarya telemetri platformu -> ROS 2 köprüsü.

WebSocket üzerinden gelen canlı batarya verisini:
- sensor_msgs/BatteryState olarak /battery_state topic'ine
- diagnostic_msgs/DiagnosticArray olarak /diagnostics topic'ine
yayınlar.

Düşük SoC, termal durum değişikliği ve arıza bilgileri diagnostic seviyelerine
eşlenir — Nav2 veya görev planlayıcı bunlara dayanarak karar alabilir
(ör. düşük SoC'de üsse dönüş).
"""

from __future__ import annotations

import asyncio
import json
import threading

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import BatteryState
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue

import websockets


class BatteryBridgeNode(Node):

    def __init__(self):
        super().__init__("battery_bridge")

        self.declare_parameter("ws_url", "ws://127.0.0.1:8000/ws/telemetry")
        self.declare_parameter("low_soc_threshold", 0.2)
        self.declare_parameter("critical_soc_threshold", 0.1)

        self._ws_url = self.get_parameter("ws_url").get_parameter_value().string_value
        self._low_soc = self.get_parameter("low_soc_threshold").get_parameter_value().double_value
        self._crit_soc = self.get_parameter("critical_soc_threshold").get_parameter_value().double_value

        self._pub_battery = self.create_publisher(BatteryState, "battery_state", 10)
        self._pub_diag = self.create_publisher(DiagnosticArray, "diagnostics", 10)

        self._ws_thread = threading.Thread(target=self._run_ws_loop, daemon=True)
        self._ws_thread.start()
        self.get_logger().info(f"Köprü başlatıldı, WS: {self._ws_url}")

    def _run_ws_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._ws_loop())

    async def _ws_loop(self):
        while rclpy.ok():
            try:
                self.get_logger().info(f"WebSocket'e bağlanılıyor: {self._ws_url}")
                async with websockets.connect(self._ws_url) as conn:
                    self.get_logger().info("WebSocket bağlantısı kuruldu.")
                    async for raw in conn:
                        if not rclpy.ok():
                            break
                        data = json.loads(raw)
                        self._publish(data)
            except Exception as e:
                self.get_logger().warn(f"WebSocket hatası: {e} — 3s sonra yeniden denenecek.")
                await asyncio.sleep(3.0)

    def _publish(self, data: dict):
        now = self.get_clock().now().to_msg()

        bs = BatteryState()
        bs.header.stamp = now
        bs.header.frame_id = data.get("pack_id", "battery")
        bs.voltage = float(data.get("pack_voltage", 0.0))
        bs.percentage = float(data.get("pack_soc", 0.0))
        bs.temperature = float(data.get("max_temperature_c", 0.0))
        bs.present = True

        cells = data.get("cells", [])
        bs.cell_voltage = [float(c["voltage"]) for c in cells]
        bs.cell_temperature = [float(c["temperature_c"]) for c in cells]

        soc = data.get("pack_soc", 1.0)
        if soc <= self._crit_soc:
            bs.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_NOT_CHARGING
            bs.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_DEAD
        else:
            bs.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_GOOD

        self._pub_battery.publish(bs)

        # --- diagnostics ---
        diag = DiagnosticArray()
        diag.header.stamp = now

        thermal = data.get("thermal_state", "normal")

        status = DiagnosticStatus()
        status.name = f"battery/{data.get('pack_id', 'PACK')}"
        status.hardware_id = data.get("pack_id", "")

        if thermal in ("critical", "shutdown"):
            status.level = DiagnosticStatus.ERROR
            status.message = f"Termal durum: {thermal.upper()}"
        elif soc <= self._crit_soc:
            status.level = DiagnosticStatus.ERROR
            status.message = f"Kritik SoC: {soc*100:.1f}%"
        elif thermal == "warning" or soc <= self._low_soc:
            status.level = DiagnosticStatus.WARN
            status.message = f"SoC: {soc*100:.1f}%, Termal: {thermal}"
        else:
            status.level = DiagnosticStatus.OK
            status.message = f"SoC: {soc*100:.1f}%, Termal: {thermal}"

        status.values = [
            KeyValue(key="pack_voltage", value=str(data.get("pack_voltage", ""))),
            KeyValue(key="pack_soc", value=f"{soc:.4f}"),
            KeyValue(key="max_temperature_c", value=str(data.get("max_temperature_c", ""))),
            KeyValue(key="soh_percent", value=str(data.get("soh_percent", ""))),
            KeyValue(key="thermal_state", value=thermal),
            KeyValue(key="cell_voltage_delta", value=str(data.get("cell_voltage_delta", ""))),
        ]

        faults = data.get("faults", {})
        if faults.get("active_fault_count", 0) > 0:
            for f in faults.get("faults", []):
                status.values.append(
                    KeyValue(key=f"fault_{f['fault_type']}", value=f"severity={f['severity']}")
                )

        diag.status.append(status)
        self._pub_diag.publish(diag)


def main(args=None):
    rclpy.init(args=args)
    node = BatteryBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
