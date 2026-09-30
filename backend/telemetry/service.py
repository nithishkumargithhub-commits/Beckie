"""Background telemetry collector and rolling history buffer.

Polls once per second and retains a 60-second rolling history for sparklines.
Supports emergency pause to immediately halt background polling.
"""

import asyncio
import logging
from collections import deque
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .models import GpuTelemetry, CpuTelemetry, TelemetrySnapshot
from .nvidia_adapter import NvidiaTelemetryAdapter
from .lhm_adapter import LibreHardwareMonitorAdapter
from .oem_adapter import OemPerformanceModeAdapter

logger = logging.getLogger("Telemetry.Service")


class TelemetryService:
    """Manages 1s hardware telemetry polling and 60-second rolling history."""

    def __init__(self, history_len: int = 60):
        self.nvidia_adapter = NvidiaTelemetryAdapter()
        self.lhm_adapter = LibreHardwareMonitorAdapter()
        self.oem_adapter = OemPerformanceModeAdapter()

        self._history: deque[Dict[str, Any]] = deque(maxlen=history_len)
        self._latest_gpu: GpuTelemetry = self.nvidia_adapter.query()
        self._latest_cpu: CpuTelemetry = self.lhm_adapter.query()
        self._is_paused: bool = False
        self._poll_task: Optional[asyncio.Task] = None
        self._running: bool = False

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def set_paused(self, paused: bool) -> None:
        self._is_paused = paused
        logger.info(f"[TelemetryService] Telemetry polling paused state set to: {paused}")

    def poll_once(self) -> TelemetrySnapshot:
        """Perform one immediate telemetry sample."""
        gpu = self.nvidia_adapter.query()
        cpu = self.lhm_adapter.query()

        # Augment CPU & GPU performance mode and fans with OEM adapter (AWCC)
        oem_mode = self.oem_adapter.query_mode()
        cpu.performanceMode = oem_mode
        if oem_mode.confidence == "exact":
            gpu.performanceMode = oem_mode

        # Query OEM fans if hardware tachometer is unavailable (e.g. Alienware EC managed)
        cpu_fan, gpu_fan = self.oem_adapter.query_fans(cpu_temp=cpu.temperatureC, gpu_temp=gpu.temperatureC)
        if not cpu.fan.available and cpu_fan is not None:
            cpu.fan = cpu_fan
        if not gpu.fan.available and gpu_fan is not None:
            gpu.fan = gpu_fan

        self._latest_gpu = gpu
        self._latest_cpu = cpu

        point = {
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "timeStr": datetime.now().strftime("%H:%M:%S"),
            "gpuUtil": gpu.utilizationPct,
            "cpuUtil": cpu.utilizationPct,
            "gpuTemp": gpu.temperatureC,
            "cpuTemp": cpu.temperatureC,
            "vramUsed": gpu.vramUsedMb,
        }
        self._history.append(point)

        return TelemetrySnapshot(gpu=gpu, cpu=cpu)

    def get_latest_snapshot(self) -> TelemetrySnapshot:
        return TelemetrySnapshot(gpu=self._latest_gpu, cpu=self._latest_cpu)

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        logger.info("[TelemetryService] Starting background 1s polling loop")
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        logger.info("[TelemetryService] Stopped background polling loop")

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                if not self._is_paused:
                    # Run synchronous queries in thread pool to avoid blocking the asyncio event loop
                    await asyncio.to_thread(self.poll_once)
            except Exception as e:
                logger.error(f"[TelemetryService] Error during poll: {e}")
            await asyncio.sleep(1.0)


_global_telemetry_service: Optional[TelemetryService] = None


def get_telemetry_service() -> TelemetryService:
    global _global_telemetry_service
    if _global_telemetry_service is None:
        _global_telemetry_service = TelemetryService()
    return _global_telemetry_service
