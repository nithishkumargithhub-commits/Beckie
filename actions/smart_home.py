import os
import json
import logging
import urllib.request
import urllib.parse
from typing import Tuple, Dict, Any
import config

logger = logging.getLogger("VoiceAssistant.SmartHome")

HASS_URL = os.getenv("HASS_URL", "http://localhost:8123")
HASS_TOKEN = os.getenv("HASS_TOKEN", "")

def control_smart_device(entity_id: str, action: str = "turn_on") -> Tuple[bool, str]:
    """
    Sends command to Home Assistant REST API for controlling smart entities (lights, switches, plugs).
    """
    token = os.getenv("HASS_TOKEN", HASS_TOKEN)
    url_base = os.getenv("HASS_URL", HASS_URL)

    if not token:
        logger.info("Home Assistant token HASS_TOKEN not set. Simulating smart home action.")
        return True, f"[Smart Home Simulated] Successfully executed '{action}' on device '{entity_id}'."

    domain = entity_id.split('.')[0] if '.' in entity_id else "homeassistant"
    endpoint = f"{url_base.rstrip('/')}/api/services/{domain}/{action}"

    payload = json.dumps({"entity_id": entity_id}).encode('utf-8')
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status in (200, 201):
                msg = f"Successfully executed '{action}' on '{entity_id}'."
                logger.info(msg)
                return True, msg
            else:
                msg = f"Smart home request returned status code {response.status}."
                logger.warning(msg)
                return False, msg
    except Exception as e:
        logger.error(f"Error controlling smart home device '{entity_id}': {e}")
        return False, f"Could not communicate with Home Assistant: {e}"

def handle_smart_home_command(user_text: str) -> Tuple[bool, str]:
    """
    Parses intent for turning on/off smart home devices.
    """
    text_lower = user_text.lower().strip()
    
    action = "turn_on"
    if "turn off" in text_lower or "switch off" in text_lower or "disable" in text_lower:
        action = "turn_off"

    # Identify entity keyword (lights, fan, switch, ac)
    if "light" in text_lower:
        entity = "light.living_room"
    elif "fan" in text_lower:
        entity = "switch.fan"
    elif "ac" in text_lower or "air conditioner" in text_lower:
        entity = "climate.air_conditioner"
    else:
        entity = "switch.smart_plug"

    return control_smart_device(entity, action)
