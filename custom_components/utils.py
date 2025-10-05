"""Utility functions for MyPlaceIQ integration."""
import json
import logging
from typing import Dict, Any, Optional
from homeassistant.core import HomeAssistant
from .const import DOMAIN

logger = logging.getLogger(__name__)

def parse_coordinator_data(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse coordinator data and return JSON body."""
    if not isinstance(data, dict) or not data or "body" not in data:
        logger.error("Invalid or missing coordinator data: %s", data)
        return None
    try:
        body = json.loads(data["body"])
        return body
    except (json.JSONDecodeError, TypeError) as err:
        logger.error("Failed to parse coordinator data body: %s", err)
        return None

def get_device_info(
    config_entry_id: str,
    entity_id: str,
    name: str,
    is_zone: bool,
    aircon_id: Optional[str] = None
) -> Dict[str, Any]:
    """Return device information for an aircon or zone."""
    device_info = {
        "identifiers": {(DOMAIN, f"{config_entry_id}_{'zone' if is_zone else 'aircon'}_{entity_id}")},
        "name": f"{'Zone' if is_zone else 'Aircon'} {name}",
        "manufacturer": "MyPlaceIQ",
        "model": "Zone" if is_zone else "Aircon",
    }
    if is_zone and aircon_id:
        device_info["via_device"] = (DOMAIN, f"{config_entry_id}_aircon_{aircon_id}")
    return device_info
