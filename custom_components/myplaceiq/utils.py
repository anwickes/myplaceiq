"""Utility functions for MyPlaceIQ integration."""
import json
import logging
from typing import Dict, Any, Optional, List, Callable
from homeassistant.core import HomeAssistant
from .const import DOMAIN

logger = logging.getLogger(__name__)

def parse_coordinator_data(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse coordinator data and return JSON body."""
    if not isinstance(data, dict) or not data or "body" not in data:
        logger.error("Invalid or missing coordinator data: %s", data)
        return None
    try:
        return json.loads(data["body"])
    except json.JSONDecodeError as err:
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

def setup_entities(
    hass: HomeAssistant,
    config_entry,
    coordinator,
    create_entities: Callable[[Dict[str, Any], Dict[str, Any], str, Dict[str, Any], str], List[Any]]
) -> List[Any]:
    """Set up entities from coordinator data."""
    body = parse_coordinator_data(coordinator.data)
    if not body:
        logger.error("Failed to parse coordinator data for entity setup")
        return []

    aircons = body.get("aircons", {})
    zones = body.get("zones", {})
    entities = []

    for aircon_id, aircon_data in aircons.items():
        entities.extend(create_entities(hass, config_entry, coordinator, aircon_id, aircon_data))
        for zone_id in aircon_data.get("zoneOrder", []):
            zone_data = zones.get(zone_id)
            if zone_data and zone_data.get("isVisible", False):
                entities.extend(create_entities(hass, config_entry, coordinator, zone_id, zone_data, aircon_id))

    if entities:
        logger.debug("Created %d entities", len(entities))
    else:
        logger.warning("No entities created; check data structure")
    return entities
