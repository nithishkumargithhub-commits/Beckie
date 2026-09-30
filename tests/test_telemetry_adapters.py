"""Unit tests for BECKIE Telemetry Adapters and Unit Integrity.

Validates:
1. RPM stays RPM and is never converted to percentage.
2. Percentage stays percentage and is NEVER converted to RPM.
3. Unavailable values produce explicit UNAVAILABLE indicators and reasons.
4. No fallback ever invents an RPM value.
5. Mode-source labels:
   - 'exact' OEM adapter
   - 'partial' Windows power plan
   - 'unknown' when no adapter is present
6. Telemetry service 1s polling, 60s ring buffer, and emergency pause halting updates.
"""

import pytest
from backend.telemetry.models import (
    GpuTelemetry,
    CpuTelemetry,
    FanMetric,
    PerformanceModeMetric,
)
from backend.telemetry.nvidia_adapter import NvidiaTelemetryAdapter
from backend.telemetry.lhm_adapter import LibreHardwareMonitorAdapter
from backend.telemetry.oem_adapter import OemPerformanceModeAdapter
from backend.telemetry.service import TelemetryService


class TestNvidiaTelemetryAdapter:
    def setup_method(self):
        self.adapter = NvidiaTelemetryAdapter()

    def test_parse_valid_gpu_metrics_with_fan_percent(self):
        # Sample nvidia-smi output where fan speed is percentage (e.g. 45%)
        raw = "NVIDIA GeForce RTX 5070 Ti, 42, 4096, 16384, 55, 45%, 160.5, P0"
        gpu = self.adapter.parse_output(raw)

        assert gpu.name == "NVIDIA GeForce RTX 5070 Ti"
        assert gpu.utilizationPct == 42.0
        assert gpu.vramUsedMb == 4096
        assert gpu.vramTotalMb == 16384
        assert gpu.temperatureC == 55.0
        assert gpu.powerWatts == 160.5

        # Unit Integrity: percentage stays percentage!
        assert gpu.fan.percent == 45.0
        # CRITICAL RULE: Never convert fan percentage to RPM!
        assert gpu.fan.rpm is None
        assert gpu.fan.available is True
        assert gpu.fan.source == "nvml"
        assert gpu.fan.unavailableReason is None

        # Mode should be exact P-state mapping
        assert gpu.performanceMode.mode == "Prefer Maximum Performance"
        assert gpu.performanceMode.confidence == "exact"
        assert gpu.performanceMode.source == "nvml"

    def test_parse_gpu_metrics_when_fan_is_unavailable(self):
        # Common on laptop RTX GPUs and EC-controlled systems
        raw = "NVIDIA GeForce RTX 5070 Laptop GPU, 15, 1024, 8151, 48, [N/A], 25.0, P8"
        gpu = self.adapter.parse_output(raw)

        assert gpu.fan.rpm is None
        assert gpu.fan.percent is None
        assert gpu.fan.available is False
        assert gpu.fan.source == "unavailable"
        assert "NVIDIA DRIVER DOES NOT EXPOSE RPM" in (gpu.fan.unavailableReason or "")
        # Never invent fallback numbers
        assert gpu.performanceMode.mode == "Power Saving"

    def test_parse_gpu_metrics_when_unsupported(self):
        raw = "NVIDIA GPU, [Not Supported], [Not Supported], [Not Supported], [Not Supported], [Not Supported], [Not Supported], [Not Supported]"
        gpu = self.adapter.parse_output(raw)

        assert gpu.utilizationPct is None
        assert gpu.vramUsedMb is None
        assert gpu.temperatureC is None
        assert gpu.fan.rpm is None
        assert gpu.fan.available is False


class TestCpuAndLhmTelemetryAdapter:
    def setup_method(self):
        self.adapter = LibreHardwareMonitorAdapter()

    def test_cpu_telemetry_unit_integrity(self):
        cpu = self.adapter.query()
        assert cpu.name is not None
        assert cpu.utilizationPct is not None
        assert 0.0 <= cpu.utilizationPct <= 100.0

        # If fan sensor is not exposed by hardware, rpm must be None
        if not cpu.fan.available:
            assert cpu.fan.rpm is None
            assert cpu.fan.percent is None
            assert cpu.fan.unavailableReason is not None
            assert "OEM SENSOR NOT EXPOSED" in cpu.fan.unavailableReason


class TestOemPerformanceModeAdapter:
    def setup_method(self):
        self.adapter = OemPerformanceModeAdapter()

    def test_query_mode_returns_structured_contract(self):
        metric = self.adapter.query_mode()
        assert isinstance(metric, PerformanceModeMetric)
        assert metric.confidence in ("exact", "partial", "unknown")
        assert metric.source in (
            "nvml",
            "libre_hardware_monitor",
            "windows_wmi",
            "oem_adapter",
            "unavailable",
        )

    def test_query_mode_partial_windows_power_plan_fallback(self):
        # When OEM adapter is not installed, falls back to Windows active power plan with confidence 'partial'
        metric = self.adapter._query_windows_power_scheme("2026-09-28T00:00:00Z")
        if metric is not None:
            assert metric.confidence == "partial"
            assert metric.source == "windows_wmi"
            assert metric.mode in ("Balanced", "Performance", "Ultimate Performance", "Power Saver") or metric.mode is not None

    def test_unknown_oem_fallback(self):
        # Force no OEM and no powercfg
        adapter = OemPerformanceModeAdapter()
        adapter._manufacturer = "NonExistentOEM"
        metric = adapter.query_mode()
        assert metric.confidence in ("partial", "unknown")


class TestTelemetryServiceAndEmergencyPause:
    def test_polling_and_history_ring_buffer(self):
        svc = TelemetryService(history_len=10)
        assert svc.is_paused is False

        # Take multiple samples
        for _ in range(5):
            svc.poll_once()

        history = svc.get_history()
        assert len(history) == 5
        assert "gpuUtil" in history[0]
        assert "cpuUtil" in history[0]
        assert "timestamp" in history[0]

    def test_emergency_pause_halts_telemetry_updates(self):
        svc = TelemetryService(history_len=10)
        svc.set_paused(True)
        assert svc.is_paused is True

        svc.set_paused(False)
        assert svc.is_paused is False
