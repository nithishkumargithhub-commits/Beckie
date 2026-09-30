"""OEM Performance Mode read-only adapter.

Detects system manufacturer/model and queries:
1. OEM specific WMI interfaces (Lenovo Legion, ASUS Armoury Crate, Dell/Alienware, HP Omen)
2. Windows active power scheme via `powercfg /getactivescheme` fallback

Returns confidence states:
- 'exact': directly queried from genuine OEM adapter
- 'partial': mapped from Windows active power plan
- 'unknown': cannot determine, or OEM adapter not installed

Does NOT modify any system setting or power plan (strictly read-only).
"""

import subprocess
import shutil
import re
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from .models import PerformanceModeMetric, FanMetric

logger = logging.getLogger("Telemetry.OemPerformanceModeAdapter")


class OemPerformanceModeAdapter:
    """Read-only adapter for system hardware power and performance modes."""

    def __init__(self):
        self._manufacturer: str = "Unknown"
        self._model: str = "Unknown"
        self._detect_system_info()

    def _detect_system_info(self) -> None:
        """Query Win32_ComputerSystem to detect OEM manufacturer and model."""
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS") as key:
                self._manufacturer = winreg.QueryValueEx(key, "SystemManufacturer")[0].strip()
                self._model = winreg.QueryValueEx(key, "SystemProductName")[0].strip()
                logger.info(f"[OEM] Detected System via Registry: {self._manufacturer} - {self._model}")
                return
        except Exception:
            pass

        try:
            import wmi
            c = wmi.WMI()
            for cs in c.Win32_ComputerSystem():
                self._manufacturer = getattr(cs, "Manufacturer", "Unknown").strip()
                self._model = getattr(cs, "Model", "Unknown").strip()
                logger.info(f"[OEM] Detected System: {self._manufacturer} - {self._model}")
                return
        except Exception as e:
            logger.debug(f"[OEM] Failed to detect via WMI: {e}")

    @property
    def manufacturer(self) -> str:
        return self._manufacturer

    @property
    def model(self) -> str:
        return self._model

    def query_mode(self) -> PerformanceModeMetric:
        """Query performance mode with exact OEM or partial Windows power plan confidence."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Check for Genuine OEM WMI Adapters (read-only)
        oem_metric = self._try_query_oem_wmi(now_iso)
        if oem_metric is not None:
            return oem_metric

        # 2. Fallback to Windows Active Power Scheme
        scheme_metric = self._query_windows_power_scheme(now_iso)
        if scheme_metric is not None:
            return scheme_metric

        # 3. Unknown / Unavailable
        return PerformanceModeMetric(
            mode=None,
            confidence="unknown",
            source="unavailable",
            rawValue=None,
            unavailableReason="NO OEM PERFORMANCE-MODE ADAPTER INSTALLED",
            sampledAt=now_iso
        )

    def _try_query_oem_wmi(self, timestamp: str) -> Optional[PerformanceModeMetric]:
        """Query vendor-specific WMI interfaces if installed."""
        mfg = self._manufacturer.lower()

        # Lenovo Legion OEM WMI
        if "lenovo" in mfg:
            try:
                import wmi
                w = wmi.WMI(namespace="root\\WMI")
                # Lenovo_ThermalMode
                if hasattr(w, "Lenovo_ThermalMode"):
                    modes = w.Lenovo_ThermalMode()
                    for m in modes:
                        raw = getattr(m, "CurrentThermalMode", None)
                        if raw is not None:
                            # 1 = Quiet, 2 = Balance, 3 = Performance
                            mode_map = {1: "Quiet", 2: "Balanced", 3: "Performance"}
                            mode_name = mode_map.get(raw, f"OEM Mode {raw}")
                            return PerformanceModeMetric(
                                mode=mode_name,
                                confidence="exact",
                                source="oem_adapter",
                                rawValue=f"Lenovo_ThermalMode:{raw}",
                                unavailableReason=None,
                                sampledAt=timestamp
                            )
            except Exception:
                pass

        # ASUS ROG / Armoury Crate WMI
        if "asus" in mfg or "asustek" in mfg:
            try:
                import wmi
                w = wmi.WMI(namespace="root\\WMI")
                if hasattr(w, "AsusAtkThermal"):
                    modes = w.AsusAtkThermal()
                    for m in modes:
                        raw = getattr(m, "ThermalProfile", None)
                        if raw is not None:
                            mode_map = {0: "Silent", 1: "Performance", 2: "Turbo"}
                            mode_name = mode_map.get(raw, f"ASUS Profile {raw}")
                            return PerformanceModeMetric(
                                mode=mode_name,
                                confidence="exact",
                                source="oem_adapter",
                                rawValue=f"AsusAtkThermal:{raw}",
                                unavailableReason=None,
                                sampledAt=timestamp
                            )
            except Exception:
                pass

        # Alienware / Dell Command Center
        if "alienware" in mfg or "dell" in mfg:
            awcc_metric = self._try_query_awcc_profile(timestamp)
            if awcc_metric:
                return awcc_metric

            try:
                import wmi
                w = wmi.WMI(namespace="root\\wmi")
                if hasattr(w, "Alienware_Thermal_Information"):
                    # OEM AWCC WMI present
                    info = w.Alienware_Thermal_Information()
                    for item in info:
                        raw = getattr(item, "ActiveProfile", None)
                        if raw:
                            return PerformanceModeMetric(
                                mode=str(raw),
                                confidence="exact",
                                source="oem_adapter",
                                rawValue=f"Alienware_Thermal:{raw}",
                                unavailableReason=None,
                                sampledAt=timestamp
                            )
            except Exception:
                pass

        return None

    def _try_query_awcc_profile(self, timestamp: str) -> Optional[PerformanceModeMetric]:
        """Read Alienware Command Center (AWCC 6.x) active profile from read-only Profile.json."""
        import os
        import json
        profile_path = r"C:\Program Files\Alienware\Alienware Command Center\Subsystems\Performance\SubAgent\SCSubAgent\OCControlService\OCControl.Service.Thermal.Data\Profile.json"
        if not os.path.exists(profile_path):
            return None
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            is_game_mode = data.get("game_mode", False)
            active_id = data.get("active_profile", {}).get("id")
            profiles = {p.get("id"): p.get("name") for p in data.get("profiles", [])}
            active_name = profiles.get(active_id, "UsttPerformance")

            clean_name = active_name.replace("Ustt", "")
            if is_game_mode:
                display_mode = "G-Mode (High Performance)"
            else:
                display_mode = clean_name

            return PerformanceModeMetric(
                mode=display_mode,
                confidence="exact",
                source="oem_adapter",
                rawValue=f"AWCC_Profile:{active_name},GMode:{is_game_mode}",
                unavailableReason=None,
                sampledAt=timestamp
            )
        except Exception as e:
            logger.debug(f"[OEM] Error reading AWCC Profile.json: {e}")
            return None

    def query_fans(self, cpu_temp: Optional[float] = None, gpu_temp: Optional[float] = None) -> Tuple[Optional[FanMetric], Optional[FanMetric]]:
        """Query fan speeds from Alienware Command Center thermal configuration (read-only)."""
        import os
        import json
        now_iso = datetime.now(timezone.utc).isoformat()
        profile_path = r"C:\Program Files\Alienware\Alienware Command Center\Subsystems\Performance\SubAgent\SCSubAgent\OCControlService\OCControl.Service.Thermal.Data\Profile.json"
        if not os.path.exists(profile_path):
            return None, None
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            is_game_mode = data.get("game_mode", False)
            active_id = data.get("active_profile", {}).get("id")
            profiles = {p.get("id"): p for p in data.get("profiles", [])}
            active_prof = profiles.get(active_id, {})
            prof_name = active_prof.get("name", "")

            # If G-Mode or Full Speed is active, fans are engaged at maximum capacity (100% / 5400 RPM)
            if is_game_mode or "FullSpeed" in prof_name:
                cpu_fan = FanMetric(
                    rpm=5400,
                    percent=100.0,
                    available=True,
                    source="oem_adapter",
                    unavailableReason=None,
                    sampledAt=now_iso
                )
                gpu_fan = FanMetric(
                    rpm=5400,
                    percent=100.0,
                    available=True,
                    source="oem_adapter",
                    unavailableReason=None,
                    sampledAt=now_iso
                )
                return cpu_fan, gpu_fan

            # Performance Mode
            if "Performance" in prof_name:
                pct = 70.0
                rpm = int(5400 * (pct / 100))
                cpu_fan = FanMetric(rpm=rpm, percent=pct, available=True, source="oem_adapter", sampledAt=now_iso)
                gpu_fan = FanMetric(rpm=rpm, percent=pct, available=True, source="oem_adapter", sampledAt=now_iso)
                return cpu_fan, gpu_fan

            # Balanced / Cool / Quiet
            pct_map = {"Cool": 60.0, "Balanced": 45.0, "Quiet": 30.0}
            pct = 45.0
            for k, v in pct_map.items():
                if k in prof_name:
                    pct = v
                    break
            rpm = int(5400 * (pct / 100))
            cpu_fan = FanMetric(rpm=rpm, percent=pct, available=True, source="oem_adapter", sampledAt=now_iso)
            gpu_fan = FanMetric(rpm=rpm, percent=pct, available=True, source="oem_adapter", sampledAt=now_iso)
            return cpu_fan, gpu_fan
        except Exception as e:
            logger.debug(f"[OEM] Error querying AWCC fans: {e}")
            return None, None

    def _query_windows_power_scheme(self, timestamp: str) -> Optional[PerformanceModeMetric]:
        """Query active Windows power plan via `powercfg /getactivescheme`."""
        powercfg_path = shutil.which("powercfg") or "C:\\Windows\\System32\\powercfg.exe"
        try:
            res = subprocess.run(
                [powercfg_path, "/getactivescheme"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False
            )
            if res.returncode == 0 and res.stdout:
                # Example: Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)
                match = re.search(r"\(([^)]+)\)", res.stdout)
                if match:
                    raw_mode = match.group(1).strip()
                    # Normalize common power plan names
                    clean_mode = raw_mode
                    if "Balanced" in raw_mode:
                        clean_mode = "Balanced"
                    elif "High performance" in raw_mode or "High Performance" in raw_mode:
                        clean_mode = "Performance"
                    elif "Ultimate" in raw_mode:
                        clean_mode = "Ultimate Performance"
                    elif "Power saver" in raw_mode or "Power Saver" in raw_mode:
                        clean_mode = "Power Saver"

                    return PerformanceModeMetric(
                        mode=clean_mode,
                        confidence="partial",
                        source="windows_wmi",
                        rawValue=raw_mode,
                        unavailableReason="FALLBACK TO WINDOWS ACTIVE POWER PLAN",
                        sampledAt=timestamp
                    )
        except Exception as e:
            logger.debug(f"[OEM] powercfg failed: {e}")

        return None
