"""
Structured JSON Logging & Performance Profiling Utility for JARVIS Voice Assistant.
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from functools import wraps

class JsonFormatter(logging.Formatter):
    """Formats log records as JSON strings."""
    def format(self, record):
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage()
        }
        if hasattr(record, "details") and isinstance(record.details, dict):
            log_obj["details"] = record.details
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

def get_logger(name: str = "Jarvis") -> logging.Logger:
    """Returns a configured logger instance with JSON formatting and console fallback."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JsonFormatter())
    logger.addHandler(console_handler)
    
    # File Handler
    try:
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        today_str = datetime.now().strftime("%Y-%m-%d")
        file_handler = logging.FileHandler(os.path.join(log_dir, f"jarvis-{today_str}.json"))
        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not setup file logging: {e}")
        
    return logger

def profile(func):
    """Decorator to measure and log function execution time in milliseconds."""
    logger = get_logger("Jarvis.Profiler")
    @wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        t_ms = (time.perf_counter() - t0) * 1000
        logger.info(f"⏱️  {func.__name__} executed in {t_ms:.1f}ms")
        return result
    return wrapper
