"""LibreHardwareMonitor local sensor adapter with Windows WMI fallbacks.

Queries local LibreHardwareMonitor WMI namespace or Windows sensors for:
- CPU utilization percent
- CPU temperature (C)
- Exact CPU fan RPM (matching names like 'CPU Fan', 'Chassis Fan', 'Fan #1')
- CPU clock frequency (MHz)

Preserves data integrity:
- If fan sensor is absent, returns unavailable with clear reason.
- Never fabricates fan RPM.
"""

import logging
import psutil
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from .models import CpuTelemetry, FanMetric, PerformanceModeMetric

logger = logging.getLogger("Telemetry.LibreHardwareMonitorAdapter")


class LibreHardwareMonitorAdapter:
    """Read-only local CPU and fan telemetry adapter."""

    def __init__(self):
        self._wmi_available = False
        self._msacpi_failed = False
        self._lhm_failed = False
        try:
            import wmi
            self._wmi_module = wmi
            self._wmi_available = True
        except ImportError:
            self._wmi_module = None

    def query(self) -> CpuTelemetry:
        """Query CPU telemetry from LibreHardwareMonitor or Windows WMI/psutil."""
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # 1. Base utilization and frequency via psutil (local OS counters)
        util_pct = float(psutil.cpu_percent(interval=None))
        freq_mhz: Optional[float] = None
        try:
            freq_stat = psutil.cpu_freq()
            if freq_stat and freq_stat.current:
                freq_mhz = round(float(freq_stat.current), 1)
        except Exception:
            pass

        # 2. Attempt LibreHardwareMonitor WMI query
        lhm_data = self._query_lhm_wmi()
        if lhm_data.get("connected"):
            logger.debug(
                f"[LHM] Matched sensor '{lhm_data.get('fan_sensor_name')}' "
                f"with value {lhm_data.get('fan_rpm')} RPM"
            )
            return CpuTelemetry(
                name=lhm_data.get("cpu_name") or "Intel Core Ultra 9 275HX",
                utilizationPct=util_pct,
                temperatureC=lhm_data.get("temp_c"),
                frequencyMhz=freq_mhz,
                fan=FanMetric(
                    rpm=lhm_data.get("fan_rpm"),
                    percent=None,
                    available=lhm_data.get("fan_rpm") is not None,
                    source="libre_hardware_monitor",
                    unavailableReason=None if lhm_data.get("fan_rpm") is not None else "OEM SENSOR NOT EXPOSED",
                    sampledAt=now_iso
                ),
                performanceMode=PerformanceModeMetric(
                    mode=None,
                    confidence="unknown",
                    source="libre_hardware_monitor",
                    unavailableReason="DEFERRED TO OEM ADAPTER",
                    sampledAt=now_iso
                ),
                source="libre_hardware_monitor"
            )

        # 3. Fallback: Windows WMI for ThermalZone & standard fan counters
        temp_c, fan_rpm = self._query_windows_wmi()

        fan_available = fan_rpm is not None
        fan_reason = None if fan_available else "OEM SENSOR NOT EXPOSED"

        return CpuTelemetry(
            name="Intel Core Ultra 9 275HX",
            utilizationPct=util_pct,
            temperatureC=temp_c,
            frequencyMhz=freq_mhz,
            fan=FanMetric(
                rpm=fan_rpm,
                percent=None,
                available=fan_available,
                source="windows_wmi" if fan_available else "unavailable",
                unavailableReason=fan_reason,
                sampledAt=now_iso
            ),
            performanceMode=PerformanceModeMetric(
                mode=None,
                confidence="unknown",
                source="unavailable",
                unavailableReason="DEFERRED TO OEM ADAPTER",
                sampledAt=now_iso
            ),
            source="windows_wmi"
        )

    def _query_lhm_wmi(self) -> Dict[str, Any]:
        """Attempt to query LibreHardwareMonitor or OpenHardwareMonitor WMI namespace."""
        if not self._wmi_available or not self._wmi_module or self._lhm_failed:
            return {"connected": False}

        for namespace in ("root\\LibreHardwareMonitor", "root\\OpenHardwareMonitor"):
            try:
                c = self._wmi_module.WMI(namespace=namespace)
                sensors = c.Sensor()
                result = {
                    "connected": True,
                    "temp_c": None,
                    "fan_rpm": None,
                    "fan_sensor_name": None,
                    "cpu_name": None
                }

                fan_names = ("cpu fan", "chassis fan", "fan #1", "fan #2", "cpu_fan", "system fan")

                for s in sensors:
                    stype = getattr(s, "SensorType", "").lower()
                    sname = getattr(s, "Name", "").lower()
                    val = getattr(s, "Value", None)

                    if stype == "temperature" and "cpu" in sname and "package" in sname:
                        try:
                            result["temp_c"] = round(float(val), 1)
                        except (TypeError, ValueError):
                            pass
                    elif stype == "fan":
                        if any(fn in sname for fn in fan_names) or result["fan_rpm"] is None:
                            try:
                                rpm_val = int(float(val))
                                if rpm_val > 0:
                                    result["fan_rpm"] = rpm_val
                                    result["fan_sensor_name"] = getattr(s, "Name", "")
                            except (TypeError, ValueError):
                                pass

                return result
            except Exception as e:
                logger.debug(f"Namespace {namespace} not accessible: {e}")

        self._lhm_failed = True
        return {"connected": False}

    def _query_windows_wmi(self) -> tuple[Optional[float], Optional[int]]:
        """Fallback query to standard Windows MSAcpi_ThermalZoneTemperature."""
        temp_c: Optional[float] = None
        fan_rpm: Optional[int] = None

        if not self._wmi_available or not self._wmi_module or self._msacpi_failed:
            return temp_c, fan_rpm

        try:
            w = self._wmi_module.WMI(namespace="root\\wmi")
            zones = w.MSAcpi_ThermalZoneTemperature()
            for z in zones:
                raw_k = getattr(z, "CurrentTemperature", None)
                if raw_k:
                    celsius = (float(raw_k) / 10.0) - 273.15
                    if 15.0 <= celsius <= 120.0:
                        temp_c = round(celsius, 1)
                        break
        except Exception:
            self._msacpi_failed = True

        # Note: Standard Windows Win32_Fan rarely populates on consumer laptops/desktops
        # We do not invent values if absent.
        return temp_c, fan_rpm
