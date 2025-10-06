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

def get_device_info(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return device information for an aircon or zone."""
    device_info = {
        "identifiers": {(DOMAIN, f"{config['config_entry_id']}_"
                                  f"{'zone' if config['is_zone'] else 'aircon'}_"
                                  f"{config['entity_id']}")},
        "name": f"{'Zone' if config['is_zone'] else 'Aircon'} {config['name']}",
        "manufacturer": "MyPlaceIQ",
        "model": "Zone" if config['is_zone'] else "Aircon",
    }
    if config['is_zone'] and config['aircon_id']:
        device_info["via_device"] = (DOMAIN, f"{config['config_entry_id']}_"
                                             f"aircon_{config['aircon_id']}")
    return device_info

def init_entity(
    entity,
    coordinator,
    myplaceiq,
    config_entry,
    entity_config: Dict[str, Any]
) -> None:
    """Initialize common entity attributes."""
    entity.coordinator = coordinator
    entity._myplaceiq = myplaceiq
    entity._config_entry = config_entry
    entity._entity_id = entity_config['entity_id']
    entity._name = entity_config.get('name', 'Zone' if entity_config['is_zone'] else 'Aircon')
    suffix = (f"_{entity_config['action']}" if entity_config['action'] else
              "_climate" if entity_config['entity_type'] == "climate" else "")
    entity._attr_unique_id = (f"{config_entry.entry_id}_"
                             f"{'zone' if entity_config['is_zone'] else 'aircon'}_"
                             f"{entity_config['entity_id']}{suffix}")
    entity._attr_name = f"{entity._name}{suffix}".replace(" ", "_").lower()
    entity._attr_icon = (
        "mdi:toggle-switch" if entity_config['is_zone'] or
        (entity_config['action'] == "toggle" and
         entity_config['entity_type'] == "button") else
        "mdi:thermostat" if entity_config['entity_type'] == "climate" else
        "mdi:air-conditioner" if entity_config['entity_type'] == "sensor" else
        "mdi:toggle-switch"
    )
    if entity_config['is_zone']:
        entity._aircon_id = entity_config['aircon_id']
    else:
        entity._aircon_id = entity_config['entity_id']

def perform_optimistic_update(
    hass: HomeAssistant,
    coordinator,
    entity_config: Dict[str, Any]
) -> None:
    """Perform an optimistic update to coordinator.data."""
    body = parse_coordinator_data(coordinator.data)
    if not body:
        logger.error("Cannot perform optimistic update: no valid data")
        return
    target_type = "zones" if entity_config['entity_type'] == "zone" else "aircons"
    if target_type in body and entity_config['entity_id'] in body[target_type]:
        body[target_type][entity_config['entity_id']][entity_config['attribute']] = \
            entity_config['new_value']
        coordinator.data = {"body": json.dumps(body)}
        if entity_config['attribute'] in ("isOn", "mode"):
            sensor_type = "state" if entity_config['attribute'] == "isOn" else "mode"
            state_sensor_id = (
                f"sensor.{body[target_type][entity_config['entity_id']]['name'].lower().replace(' ', '_')}_"
                f"{sensor_type}"
            )
            hass.async_create_task(
                hass.services.async_call(
                    "homeassistant", "update_entity",
                    {"entity_id": state_sensor_id}
                )
            )
        logger.debug(
            "Optimistically updated %s %s %s to %s",
            target_type[:-1], entity_config['entity_id'],
            entity_config['attribute'], entity_config['new_value']
        )
    else:
        logger.warning(
            "Could not perform optimistic update for %s %s %s: not found in data",
            target_type[:-1], entity_config['entity_id'], entity_config['attribute']
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
