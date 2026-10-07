import json
import logging
import time
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

logger = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MyPlaceIQ binary sensor entities from a config entry."""
    logger.debug("Setting up binary sensor entities for MyPlaceIQ")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    data = coordinator.data

    if not isinstance(data, dict) or not data or "body" not in data:
        logger.error("Invalid or missing coordinator data: %s", data)
        return

    try:
        body = json.loads(data["body"])
    except (json.JSONDecodeError, TypeError) as err:
        logger.error("Failed to parse coordinator data body: %s", err)
        return

    aircons = body.get("aircons", {})
    zones = body.get("zones", {})

    entities = []

    # Aircon on/off state
    for aircon_id, aircon_data in aircons.items():
        entities.append(
            MyPlaceIQAirconStateBinarySensor(
                coordinator=coordinator,
                config_entry=config_entry,
                aircon_id=aircon_id,
                aircon_data=aircon_data,
            )
        )

    # Per-zone: on/off state and priority state
    for aircon_id, aircon_data in aircons.items():
        for zone_id in aircon_data.get("zoneOrder", []):
            zone_data = zones.get(zone_id)
            if not zone_data or not zone_data.get("isVisible", False):
                continue

            entities.append(
                MyPlaceIQZoneStateBinarySensor(
                    coordinator=coordinator,
                    config_entry=config_entry,
                    zone_id=zone_id,
                    zone_data=zone_data,
                    aircon_id=aircon_id,
                )
            )

            if zone_data.get("isPriorityZoneAllowed", False):
                entities.append(
                    MyPlaceIQZonePriorityBinarySensor(
                        coordinator=coordinator,
                        config_entry=config_entry,
                        zone_id=zone_id,
                        zone_data=zone_data,
                        aircon_id=aircon_id,
                    )
                )

    if entities:
        async_add_entities(entities)
        logger.debug("Added %d binary sensor entities", len(entities))
    else:
        logger.warning("No binary sensor entities created; check data structure")


class MyPlaceIQAirconStateBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for MyPlaceIQ AC system on/off state."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, coordinator, config_entry, aircon_id, aircon_data):
        super().__init__(coordinator)
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = aircon_data.get("name", "Aircon")
        self._last_known_is_on = None
        self._attr_unique_id = f"{config_entry.entry_id}_aircon_{aircon_id}_state"
        self._attr_has_entity_name = True
        self._attr_name = "HVAC State"
        self._attr_device_class = BinarySensorDeviceClass.POWER
        self._attr_icon = "mdi:power"

    @property
    def is_on(self):
        """Return True when the AC is on."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return False
        try:
            body = json.loads(data["body"])
            aircon = body.get("aircons", {}).get(self._aircon_id, {})
            is_on = aircon.get("isOn",
                self._last_known_is_on if self._last_known_is_on is not None else False)
            if is_on:
                self._last_known_is_on = is_on
            logger.debug("Aircon %s state updated at %s: %s",
                         self._attr_unique_id, time.strftime("%H:%M:%S"), is_on)
            return bool(is_on)
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse aircon state for %s: %s", self._attr_unique_id, err)
            return False

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}")},
            "name": f"Aircon {self._name}",
            "manufacturer": "MyPlaceIQ",
            "model": "Aircon",
        }


class MyPlaceIQZoneStateBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for MyPlaceIQ zone on/off state."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, coordinator, config_entry, zone_id, zone_data, aircon_id):
        # pylint: disable=too-many-arguments, too-many-positional-arguments
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = zone_data.get("name", "Zone")
        self._attr_unique_id = f"{config_entry.entry_id}_zone_{zone_id}_state"
        self._attr_has_entity_name = True
        self._attr_name = "HVAC State"
        self._attr_device_class = BinarySensorDeviceClass.POWER
        self._attr_icon = "mdi:toggle-switch"

    @property
    def is_on(self):
        """Return True when the zone is on."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return False
        try:
            body = json.loads(data["body"])
            zone = body.get("zones", {}).get(self._zone_id, {})
            is_on = zone.get("isOn", False)
            logger.debug("Zone %s state updated at %s: %s",
                         self._attr_unique_id, time.strftime("%H:%M:%S"), is_on)
            return bool(is_on)
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse zone state for %s: %s", self._attr_unique_id, err)
            return False

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_zone_{self._zone_id}")},
            "name": f"Zone {self._name}",
            "manufacturer": "MyPlaceIQ",
            "model": "Zone",
            "via_device": (DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}"),
        }


class MyPlaceIQZonePriorityBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating whether a zone currently has priority enabled."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, coordinator, config_entry, zone_id, zone_data, aircon_id):
        # pylint: disable=too-many-arguments, too-many-positional-arguments
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = zone_data.get("name", "Zone")
        self._attr_unique_id = f"{config_entry.entry_id}_zone_{zone_id}_priority"
        self._attr_has_entity_name = True
        self._attr_name = "HVAC Priority"

    @property
    def is_on(self):
        """Return True when this zone has priority enabled."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return False
        try:
            body = json.loads(data["body"])
            zone = body.get("zones", {}).get(self._zone_id, {})
            is_priority = zone.get("isPriorityZone", False)
            logger.debug("Zone %s priority is_on: %s", self._zone_id, is_priority)
            return bool(is_priority)
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse priority state for zone %s: %s", self._zone_id, err)
            return False

    @property
    def icon(self):
        """Return a filled star when priority is active, outlined when not."""
        return "mdi:star" if self.is_on else "mdi:star-outline"

    @property
    def device_info(self):
        """Return device information — attach to the zone device."""
        return {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_zone_{self._zone_id}")},
            "name": f"Zone {self._name}",
            "manufacturer": "MyPlaceIQ",
            "model": "Zone",
            "via_device": (DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}"),
        }
