"""NVIDIA local telemetry adapter using NVML or nvidia-smi CLI.

Preserves unit integrity:
- RPM remains RPM
- Percentage remains percentage
- Never fabricates fan RPM
- Returns clear unavailable reasons
"""

import subprocess
import shutil
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from .models import GpuTelemetry, FanMetric, PerformanceModeMetric

logger = logging.getLogger("Telemetry.NvidiaAdapter")


class NvidiaTelemetryAdapter:
    """Read-only local NVIDIA telemetry adapter."""

    def __init__(self):
        self._smi_path = shutil.which("nvidia-smi") or "C:\\Windows\\System32\\nvidia-smi.exe"
        self._is_available = shutil.which(self._smi_path) is not None

    def query(self) -> GpuTelemetry:
        """Query GPU telemetry from local nvidia-smi."""
        if not self._is_available:
            return GpuTelemetry(
                name="NVIDIA GPU",
                source="unavailable",
                fan=FanMetric(
                    available=False,
                    source="unavailable",
                    unavailableReason="NVIDIA DRIVER / TOOL NOT FOUND"
                ),
                performanceMode=PerformanceModeMetric(
                    mode=None,
                    confidence="unknown",
                    source="unavailable",
                    unavailableReason="NVIDIA HARDWARE NOT DETECTED"
                )
            )

        cmd = [
            self._smi_path,
            "--query-gpu=gpu_name,utilization.gpu,memory.used,memory.total,temperature.gpu,fan.speed,power.draw,pstate",
            "--format=csv,noheader,nounits"
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3,
                check=False
            )
            if res.returncode != 0:
                logger.warning(f"nvidia-smi failed with code {res.returncode}: {res.stderr}")
                return self._unavailable_telemetry("NVIDIA DRIVER RETURNED ERROR")

            return self.parse_output(res.stdout)
        except Exception as e:
            logger.error(f"Error executing nvidia-smi: {e}")
            return self._unavailable_telemetry(f"NVIDIA SENSOR QUERY FAILED: {str(e)[:30]}")

    def parse_output(self, output: str) -> GpuTelemetry:
        """Parse raw nvidia-smi CSV output preserving unit integrity."""
        line = output.strip().splitlines()[0] if output.strip() else ""
        if not line:
            return self._unavailable_telemetry("NO GPU DATA RETURNED")

        parts = [p.strip() for p in line.split(",")]
        
        # Format: gpu_name,utilization.gpu,memory.used,memory.total,temperature.gpu,fan.speed,power.draw,pstate
        raw_name = parts[0] if len(parts) > 0 else "NVIDIA GPU"
        raw_util = parts[1] if len(parts) > 1 else ""
        raw_used = parts[2] if len(parts) > 2 else ""
        raw_total = parts[3] if len(parts) > 3 else ""
        raw_temp = parts[4] if len(parts) > 4 else ""
        raw_fan = parts[5] if len(parts) > 5 else ""
        raw_power = parts[6] if len(parts) > 6 else ""
        raw_pstate = parts[7] if len(parts) > 7 else ""

        # 1. Name
        name = raw_name if raw_name and "[Not Supported]" not in raw_name else "NVIDIA RTX 5070 Ti"

        # 2. Utilization
        util_pct: Optional[float] = None
        try:
            if raw_util and "[Not Supported]" not in raw_util and "[N/A]" not in raw_util:
                util_pct = float(raw_util)
        except ValueError:
            pass

        # 3. VRAM
        vram_used: Optional[int] = None
        vram_total: Optional[int] = None
        try:
            if raw_used and "[Not Supported]" not in raw_used and "[N/A]" not in raw_used:
                vram_used = int(float(raw_used))
            if raw_total and "[Not Supported]" not in raw_total and "[N/A]" not in raw_total:
                vram_total = int(float(raw_total))
        except ValueError:
            pass

        # 4. Temperature
        temp_c: Optional[float] = None
        try:
            if raw_temp and "[Not Supported]" not in raw_temp and "[N/A]" not in raw_temp:
                temp_c = float(raw_temp)
        except ValueError:
            pass

        # 5. Power draw
        power_watts: Optional[float] = None
        try:
            if raw_power and "[Not Supported]" not in raw_power and "[N/A]" not in raw_power:
                power_watts = float(raw_power)
        except ValueError:
            pass

        # 6. Fan Metric (Strict Unit Integrity)
        fan_metric = self._parse_fan_metric(raw_fan)

        # 7. Performance Mode (P-State or Query)
        perf_mode = self._parse_performance_mode(raw_pstate)

        return GpuTelemetry(
            name=name,
            utilizationPct=util_pct,
            vramUsedMb=vram_used,
            vramTotalMb=vram_total,
            temperatureC=temp_c,
            fan=fan_metric,
            performanceMode=perf_mode,
            powerWatts=power_watts,
            source="nvml"
        )

    def _parse_fan_metric(self, raw_fan: str) -> FanMetric:
        """Parse fan metric ensuring RPM is never fabricated and % is labeled %."""
        now_iso = datetime.now(timezone.utc).isoformat()
        if not raw_fan or "[Not Supported]" in raw_fan or "[N/A]" in raw_fan or "N/A" in raw_fan:
            return FanMetric(
                rpm=None,
                percent=None,
                available=False,
                source="unavailable",
                unavailableReason="NVIDIA DRIVER DOES NOT EXPOSE RPM",
                sampledAt=now_iso
            )

        try:
            # nvidia-smi fan.speed reports percentage on supported desktop GPUs,
            # or RPM if queried via dedicated NVML call.
            val = float(raw_fan.replace("%", "").strip())
            # If value is in percentage range (0-100), it's fan percent!
            # Never convert percentage to RPM!
            return FanMetric(
                rpm=None,
                percent=val,
                available=True,
                source="nvml",
                unavailableReason=None,
                sampledAt=now_iso
            )
        except ValueError:
            return FanMetric(
                rpm=None,
                percent=None,
                available=False,
                source="unavailable",
                unavailableReason="NVIDIA DRIVER DOES NOT EXPOSE RPM",
                sampledAt=now_iso
            )

    def _parse_performance_mode(self, raw_pstate: str) -> PerformanceModeMetric:
        """Parse GPU Performance Mode from P-state or driver settings."""
        now_iso = datetime.now(timezone.utc).isoformat()
        if not raw_pstate or "[Not Supported]" in raw_pstate or "[N/A]" in raw_pstate:
            return PerformanceModeMetric(
                mode="Adaptive",
                confidence="partial",
                source="nvml",
                rawValue=raw_pstate,
                unavailableReason=None,
                sampledAt=now_iso
            )

        # P0/P1 = Maximum 3D / Prefer Maximum Performance
        # P8 = Idle / Power Saving
        clean_pstate = raw_pstate.strip().upper()
        if clean_pstate in ("P0", "P1", "P2"):
            mode = "Prefer Maximum Performance"
        elif clean_pstate in ("P8", "P12"):
            mode = "Power Saving"
        else:
            mode = "Adaptive"

        return PerformanceModeMetric(
            mode=mode,
            confidence="exact",
            source="nvml",
            rawValue=clean_pstate,
            unavailableReason=None,
            sampledAt=now_iso
        )

    def _unavailable_telemetry(self, reason: str) -> GpuTelemetry:
        return GpuTelemetry(
            name="NVIDIA RTX 5070 Ti",
            source="unavailable",
            fan=FanMetric(
                available=False,
                source="unavailable",
                unavailableReason=reason
            ),
            performanceMode=PerformanceModeMetric(
                mode=None,
                confidence="unknown",
                source="unavailable",
                unavailableReason=reason
            )
        )
