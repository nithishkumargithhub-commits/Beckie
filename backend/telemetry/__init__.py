"""BECKIE Telemetry package."""

from .models import (
    TelemetrySource,
    FanMetric,
    PerformanceModeMetric,
    GpuTelemetry,
    CpuTelemetry,
    TelemetrySnapshot,
)
from .nvidia_adapter import NvidiaTelemetryAdapter
from .lhm_adapter import LibreHardwareMonitorAdapter
from .oem_adapter import OemPerformanceModeAdapter
from .service import TelemetryService, get_telemetry_service

__all__ = [
    "TelemetrySource",
    "FanMetric",
    "PerformanceModeMetric",
    "GpuTelemetry",
    "CpuTelemetry",
    "TelemetrySnapshot",
    "NvidiaTelemetryAdapter",
    "LibreHardwareMonitorAdapter",
    "OemPerformanceModeAdapter",
    "TelemetryService",
    "get_telemetry_service",
]
