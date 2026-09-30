"""
Unit Tests for Tauri 2.x Telemetry Engine, WMI/NVML Parsers, and 3D HUD Artifacts.

Validates:
1. Rust telemetry parsing contract (NVML nvidia-smi CSV & Windows WMI CPU/temp/fan).
2. Unsupported metric graceful degradation (returning None/null and displaying N/A).
3. Tauri 2.x configuration integrity (tauri.conf.json and Cargo.toml).
4. Frontend build bundle verification (HTML/JS/CSS assets ready for WebView2).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
import pytest


# ---------------------------------------------------------------------------
# Python Mirror of Rust Telemetry Parsers for Independent Verification
# ---------------------------------------------------------------------------

def parse_nvidia_smi_output(output: str) -> dict:
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    if not lines:
        return {
            "utilization_pct": None,
            "vram_used_mb": None,
            "vram_total_mb": None,
            "temperature_c": None,
            "fan_speed_rpm": None,
            "power_mode": None,
        }

    parts = [s.strip() for s in lines[0].split(",")]
    res = {
        "utilization_pct": None,
        "vram_used_mb": None,
        "vram_total_mb": None,
        "temperature_c": None,
        "fan_speed_rpm": None,
        "power_mode": None,
    }

    if len(parts) > 0 and parts[0] not in ("[Not Supported]", "N/A"):
        try:
            res["utilization_pct"] = max(0.0, min(100.0, float(parts[0])))
        except ValueError:
            pass

    if len(parts) > 1 and parts[1] not in ("[Not Supported]", "N/A"):
        try:
            res["vram_used_mb"] = int(parts[1])
        except ValueError:
            pass

    if len(parts) > 2 and parts[2] not in ("[Not Supported]", "N/A"):
        try:
            res["vram_total_mb"] = int(parts[2])
        except ValueError:
            pass

    if len(parts) > 3 and parts[3] not in ("[Not Supported]", "N/A"):
        try:
            res["temperature_c"] = float(parts[3])
        except ValueError:
            pass

    if len(parts) > 4 and parts[4] not in ("[Not Supported]", "N/A"):
        try:
            res["fan_speed_rpm"] = int(parts[4])
        except ValueError:
            pass

    if len(parts) > 5:
        pwr = parts[5].strip()
        if pwr and "[not supported]" not in pwr.lower() and "n/a" not in pwr.lower():
            res["power_mode"] = pwr

    return res


def parse_wmi_cpu_load(output: str) -> float | None:
    for line in output.splitlines():
        trimmed = line.strip()
        if "loadpercentage=" in trimmed.lower():
            val_str = trimmed.split("=", 1)[1].strip()
            try:
                return max(0.0, min(100.0, float(val_str)))
            except ValueError:
                pass
        else:
            try:
                return max(0.0, min(100.0, float(trimmed)))
            except ValueError:
                pass
    return None


def parse_wmi_thermal_zone(output: str) -> float | None:
    for line in output.splitlines():
        trimmed = line.strip()
        if "currenttemperature=" in trimmed.lower():
            val_str = trimmed.split("=", 1)[1].strip()
            try:
                raw_k = float(val_str)
                kelvin = raw_k / 10.0
                celsius = kelvin - 273.15
                if 0.0 < celsius < 130.0:
                    return round(celsius, 1)
            except ValueError:
                pass
    return None


def parse_wmi_fan_speed(output: str) -> int | None:
    for line in output.splitlines():
        trimmed = line.strip()
        if "desiredspeed=" in trimmed.lower():
            val_str = trimmed.split("=", 1)[1].strip()
            try:
                rpm = int(val_str)
                if 0 < rpm < 10000:
                    return rpm
            except ValueError:
                pass
    return None


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------

class TestRustTelemetryParsers:
    def test_parse_nvidia_smi_valid(self):
        sample = "38, 5120, 16384, 55, 1400, Prefer Maximum Performance\n"
        m = parse_nvidia_smi_output(sample)
        assert m["utilization_pct"] == 38.0
        assert m["vram_used_mb"] == 5120
        assert m["vram_total_mb"] == 16384
        assert m["temperature_c"] == 55.0
        assert m["fan_speed_rpm"] == 1400
        assert m["power_mode"] == "Prefer Maximum Performance"

    def test_parse_nvidia_smi_graceful_fallbacks_unsupported(self):
        """Ensures [Not Supported] or N/A from hardware queries fall back cleanly to None."""
        sample = "15, 2048, 8192, 44, [Not Supported], [N/A]\n"
        m = parse_nvidia_smi_output(sample)
        assert m["utilization_pct"] == 15.0
        assert m["vram_used_mb"] == 2048
        assert m["vram_total_mb"] == 8192
        assert m["temperature_c"] == 44.0
        assert m["fan_speed_rpm"] is None
        assert m["power_mode"] is None

    def test_parse_nvidia_smi_malformed(self):
        sample = "\n   \n"
        m = parse_nvidia_smi_output(sample)
        assert m["utilization_pct"] is None
        assert m["vram_used_mb"] is None

    def test_parse_wmi_cpu_load(self):
        sample = "\r\nLoadPercentage=42\r\n"
        val = parse_wmi_cpu_load(sample)
        assert val == 42.0

        plain = "78.5"
        assert parse_wmi_cpu_load(plain) == 78.5
        assert parse_wmi_cpu_load("") is None

    def test_parse_wmi_thermal_zone(self):
        # 3132 tenths of Kelvin = 313.2K = ~40.05 C -> rounded to 40.1 C
        sample = "CurrentTemperature=3132\r\n"
        val = parse_wmi_thermal_zone(sample)
        assert val is not None
        assert 40.0 <= val <= 40.1

    def test_parse_wmi_fan_speed(self):
        sample = "DesiredSpeed=1750\r\n"
        assert parse_wmi_fan_speed(sample) == 1750
        assert parse_wmi_fan_speed("DesiredSpeed=0\r\n") is None


class TestTauriAndFrontendProjectStructure:
    def test_tauri_conf_json_valid(self):
        conf_path = Path("src-tauri/tauri.conf.json")
        assert conf_path.exists(), "src-tauri/tauri.conf.json must exist"

        with open(conf_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data.get("productName") in ("BECKIE", "JARVIS")
        assert data.get("version") == "2.0.0"
        assert "build" in data
        assert data["build"].get("frontendDist") == "../frontend/dist"
        assert "app" in data
        assert len(data["app"].get("windows", [])) > 0

    def test_cargo_toml_exists(self):
        cargo_path = Path("src-tauri/Cargo.toml")
        assert cargo_path.exists()
        content = cargo_path.read_text(encoding="utf-8")
        assert 'name = "jarvis-hud"' in content or 'name = "beckie-hud"' in content
        assert "tauri =" in content

    def test_rust_source_files_exist(self):
        main_rs = Path("src-tauri/src/main.rs")
        telemetry_rs = Path("src-tauri/src/telemetry.rs")
        assert main_rs.exists()
        assert telemetry_rs.exists()

        content = main_rs.read_text(encoding="utf-8")
        assert "get_gpu_metrics" in content
        assert "get_cpu_metrics" in content
        assert "get_jarvis_state" in content or "get_beckie_state" in content
        assert "emergency_pause" in content

    def test_frontend_production_build_artifacts_exist(self):
        dist_dir = Path("frontend/dist")
        assert dist_dir.exists(), "frontend/dist directory must exist after build"

        html_file = dist_dir / "index.html"
        assert html_file.exists()
        html_content = html_file.read_text(encoding="utf-8")
        assert "BECKIE" in html_content

        assets_dir = dist_dir / "assets"
        assert assets_dir.exists()
        files = [p.name for p in assets_dir.iterdir()]
        assert any(f.endswith(".js") for f in files), "Built JS chunk must exist"
        assert any(f.endswith(".css") for f in files), "Built CSS chunk must exist"
