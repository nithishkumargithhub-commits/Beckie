import psutil
import logging

logger = logging.getLogger("VoiceAssistant.SystemHealth")

def get_system_health() -> str:
    """
    Retrieves system performance stats: CPU, RAM, Battery, and C: drive disk space.
    """
    logger.info("Retrieving system performance metrics...")
    try:
        # 1. CPU Load
        cpu = psutil.cpu_percent(interval=0.1)
        
        # 2. Virtual Memory
        ram = psutil.virtual_memory().percent
        
        # 3. Battery Info
        battery = psutil.sensors_battery()
        battery_str = ""
        if battery:
            plugged = "plugged in" if battery.power_plugged else "not plugged in"
            battery_str = f"Your battery is at {battery.percent} percent and is {plugged}. "
        else:
            battery_str = "Battery information is not available. "
            
        # 4. Storage Space (C: drive)
        try:
            disk = psutil.disk_usage('C:\\')
            disk_free_gb = disk.free / (1024 ** 3)
            disk_percent = disk.percent
            disk_str = f"Your C drive has {disk_free_gb:.1f} gigabytes free, which is {100 - disk_percent:.1f} percent available."
        except Exception as disk_err:
            logger.warning(f"Disk check failed for C drive: {disk_err}")
            disk_str = "Storage information is not available."
            
        msg = (
            f"Here is your system health report. "
            f"CPU utilization is currently at {cpu} percent. "
            f"Memory usage is at {ram} percent. "
            f"{battery_str}"
            f"{disk_str}"
        )
        return msg
    except Exception as e:
        logger.error(f"Error fetching system health: {e}")
        return "Sorry, I encountered an error while trying to read your system metrics."
