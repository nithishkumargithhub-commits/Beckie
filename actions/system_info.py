"""
Offline System Info Telemetry Action using psutil.
Execution latency: ~30ms
"""

import psutil
from logger import profile, get_logger

logger = get_logger("Jarvis.Actions.SystemInfo")

@profile
def get_system_info(metric: str = "all") -> str:
    """Queries system telemetry (CPU, RAM, Battery, Disk)."""
    metric = metric.lower().strip()
    try:
        if "cpu" in metric:
            cpu_pct = psutil.cpu_percent(interval=None)
            return f"CPU utilization is currently at {cpu_pct} percent."
        elif "memory" in metric or "ram" in metric:
            ram = psutil.virtual_memory()
            return f"Memory usage is at {ram.percent} percent."
        elif "battery" in metric:
            battery = psutil.sensors_battery()
            if battery:
                status = "plugged in" if battery.power_plugged else "on battery"
                return f"Battery is at {battery.percent} percent and {status}."
            return "Battery information unavailable."
        elif "disk" in metric:
            disk = psutil.disk_usage('/')
            return f"Disk usage is at {disk.percent} percent with {disk.free // (1024**3)} gigabytes free."
        else:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            return f"CPU usage is {cpu} percent and Memory usage is {ram} percent."
    except Exception as e:
        logger.error(f"Error fetching system info: {e}")
        return "Could not fetch system info."
