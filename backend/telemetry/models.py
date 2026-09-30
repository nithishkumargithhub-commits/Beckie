"""Telemetry data models matching the BECKIE HUD 3D data contract."""

from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime, timezone

TelemetrySource = Literal[
    "nvml",
    "libre_hardware_monitor",
    "windows_wmi",
    "oem_adapter",
    "unavailable"
]

ConfidenceLevel = Literal["exact", "partial", "unknown"]


class FanMetric(BaseModel):
    rpm: Optional[int] = None
    percent: Optional[float] = None
    available: bool = False
    source: TelemetrySource = "unavailable"
    unavailableReason: Optional[str] = None
    sampledAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PerformanceModeMetric(BaseModel):
    mode: Optional[str] = None
    confidence: ConfidenceLevel = "unknown"
    source: TelemetrySource = "unavailable"
    rawValue: Optional[str] = None
    unavailableReason: Optional[str] = None
    sampledAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GpuTelemetry(BaseModel):
    name: Optional[str] = "NVIDIA RTX 5070 Ti"
    utilizationPct: Optional[float] = None
    vramUsedMb: Optional[int] = None
    vramTotalMb: Optional[int] = None
    temperatureC: Optional[float] = None
    fan: FanMetric = Field(default_factory=FanMetric)
    performanceMode: PerformanceModeMetric = Field(default_factory=PerformanceModeMetric)
    powerWatts: Optional[float] = None
    source: TelemetrySource = "unavailable"


class CpuTelemetry(BaseModel):
    name: Optional[str] = "Intel Core Ultra 9 275HX"
    utilizationPct: Optional[float] = None
    temperatureC: Optional[float] = None
    frequencyMhz: Optional[float] = None
    fan: FanMetric = Field(default_factory=FanMetric)
    performanceMode: PerformanceModeMetric = Field(default_factory=PerformanceModeMetric)
    source: TelemetrySource = "unavailable"


class TelemetrySnapshot(BaseModel):
    gpu: GpuTelemetry
    cpu: CpuTelemetry
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
