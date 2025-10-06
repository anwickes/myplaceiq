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

def init_entity(
    entity,
    coordinator,
    myplaceiq,
    config_entry,
    entity_id: str,
    entity_data: Dict[str, Any],
    entity_type: str,
    action: Optional[str] = None,
    is_zone: bool = False,
    aircon_id: Optional[str] = None
) -> None:
    """Initialize common entity attributes."""
    entity.coordinator = coordinator
    entity._myplaceiq = myplaceiq
    entity._config_entry = config_entry
    entity._entity_id = entity_id
    entity._name = entity_data.get("name", "Zone" if is_zone else "Aircon")
    suffix = f"_{action}" if action else "_climate" if entity_type == "climate" else ""
    entity._attr_unique_id = (
        f"{config_entry.entry_id}_{'zone' if is_zone else 'aircon'}_{entity_id}{suffix}"
    )
    entity._attr_name = f"{entity._name}{suffix}".replace(" ", "_").lower()
    entity._attr_icon = (
        "mdi:toggle-switch" if is_zone or (action == "toggle" and entity_type == "button") else
        "mdi:thermostat" if entity_type == "climate" else
        "mdi:air-conditioner" if entity_type == "sensor" else "mdi:toggle-switch"
    )
    if is_zone:
        entity._aircon_id = aircon_id
    else:
        entity._aircon_id = entity_id

def perform_optimistic_update(
    hass: HomeAssistant,
    coordinator,
    entity_type: str,
    entity_id: str,
    attribute: str,
    new_value: Any
) -> None:
    """Perform an optimistic update to coordinator.data."""
    body = parse_coordinator_data(coordinator.data)
    if not body:
        logger.error("Cannot perform optimistic update: no valid data")
        return
    target_type = "zones" if entity_type == "zone" else "aircons"
    if target_type in body and entity_id in body[target_type]:
        body[target_type][entity_id][attribute] = new_value
        coordinator.data = {"body": json.dumps(body)}
        if attribute in ("isOn", "mode"):
            sensor_type = "state" if attribute == "isOn" else "mode"
            state_sensor_id = (
                f"sensor.{body[target_type][entity_id]['name'].lower().replace(' ', '_')}_{sensor_type}"
            )
            hass.async_create_task(
                hass.services.async_call(
                    "homeassistant", "update_entity",
                    {"entity_id": state_sensor_id}
                )
            )
        logger.debug(
            "Optimistically updated %s %s %s to %s",
            target_type[:-1], entity_id, attribute, new_value
        )
    else:
        logger.warning(
            "Could not perform optimistic update for %s %s %s: not found in data",
            target_type[:-1], entity_id, attribute
        )

def setup_entities(
    hass: HomeAssistant,
    config_entry,
    coordinator,
    create_entities: Callable[[HomeAssistant, Any, Any, str, Dict[str, Any], Optional[str]], List[Any]]
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
