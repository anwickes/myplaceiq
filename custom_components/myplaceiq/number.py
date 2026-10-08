import json
import logging
import math
from typing import Callable, NamedTuple
from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .energy_settings import (
    NOMINAL_VOLTAGE_V,
    MyPlaceIQEnergySettingsEntity,
    iqe_aircon_id,
    iqe_supported,
)

logger = logging.getLogger(__name__)


class NumberSpec(NamedTuple):
    """One IQe number setting.

    read(settings, aircon_id) returns the value shown in Home Assistant (or
    None when the hub has no value yet); write(settings, value, aircon_id)
    stores a Home Assistant value into the hub's units.
    """

    key: str
    name: str
    icon: str
    unit: str
    device_class: NumberDeviceClass
    min_value: float
    max_value: float
    step: float
    read: Callable
    write: Callable
    per_aircon: bool = False
    enabled_field: str | None = None


def _kw_spec(key, name, icon, field):
    """Build a spec for a kW setting stored by the hub in watts."""
    return NumberSpec(
        key=key, name=name, icon=icon, unit=UnitOfPower.KILO_WATT,
        device_class=NumberDeviceClass.POWER, min_value=0, max_value=100, step=0.1,
        read=lambda s, _a: s[field] / 1000 if field in s else None,
        write=lambda s, v, _a: s.__setitem__(field, int(round(v * 1000))),
    )


def _trigger_spec(key, name, icon, field, min_value, max_value, enabled_field):
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    """Build a spec for an outdoor-temperature trigger.

    The ranges match the limits the official app enforces; the hub's own
    limits are not known.
    """
    return NumberSpec(
        key=key, name=name, icon=icon, unit=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        min_value=min_value, max_value=max_value, step=1,
        read=lambda s, _a: s.get(field),
        write=lambda s, v, _a: s.__setitem__(field, float(v)),
        enabled_field=enabled_field,
    )


# Wizard step -> field, confirmed by capture and the app's setup screens.
# Note: choosing "No" to solar panels in the app sets BOTH solarPanelW and
# maxInverterPowerW to 0 (confirmed by capture), so for the same result set
# both of these numbers to 0.
HUB_NUMBER_SPECS = (
    _kw_spec("solar_panel", "Solar Panel", "mdi:solar-panel", "solarPanelW"),
    _kw_spec("inverter_capacity", "Inverter Capacity", "mdi:flash", "maxInverterPowerW"),
    _kw_spec("household_power", "Household Power Use", "mdi:home-lightning-bolt", "fixedBaselineW"),
    _trigger_spec(
        "cool_trigger", "Cooling Starts Above", "mdi:snowflake-thermometer",
        "smartAirCoolTrigger", 20, 50, "smartAirCoolOn",
    ),
    _trigger_spec(
        "heat_trigger", "Heating Starts Below", "mdi:sun-thermometer",
        "smartAirHeatTrigger", -20, 30, "smartAirHeatOn",
    ),
)

# The hub stores each aircon's draw in watts; the app asks for amps and
# converts at a fixed nominal voltage.
RUNNING_CURRENT_SPEC = NumberSpec(
    key="running_current", name="Running Current", icon="mdi:current-ac",
    unit=UnitOfElectricCurrent.AMPERE, device_class=NumberDeviceClass.CURRENT,
    min_value=0, max_value=100, step=0.1,
    read=lambda s, a: (
        s["airconPowerTableW"][a] / NOMINAL_VOLTAGE_V
        if a in s.get("airconPowerTableW", {}) else None
    ),
    write=lambda s, v, a: s.setdefault("airconPowerTableW", {}).__setitem__(
        a, int(round(v * NOMINAL_VOLTAGE_V))
    ),
    per_aircon=True,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MyPlaceIQ number entities from a config entry.

    The entities exist whenever the hub supports IQe. The trigger for a mode
    that is off is hidden (not removed), so nothing turns "unavailable"
    after a restart; see MyPlaceIQEnergySettingsEntity.
    """
    logger.debug("Setting up number entities for MyPlaceIQ")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    myplaceiq = hass.data[DOMAIN][config_entry.entry_id]["myplaceiq"]

    try:
        body = json.loads(coordinator.data["body"])
    except (KeyError, TypeError, ValueError) as err:
        logger.error("Failed to parse coordinator data body: %s", err)
        return

    if not iqe_supported(body):
        logger.debug("IQe is not supported by this hub; no number entities created")
        return

    entities = _iqe_number_entities(coordinator, myplaceiq, config_entry, body)
    async_add_entities(entities)
    logger.debug("Added %d IQe number entities", len(entities))


def _iqe_number_entities(coordinator, myplaceiq, config_entry, body):
    """Build IQe number entities from the current hub state."""
    aircons = body.get("aircons", {})
    hub_aircon_id = iqe_aircon_id(body)
    entities = []

    if hub_aircon_id is not None:
        name = aircons[hub_aircon_id].get("name", "Aircon")
        entities.extend(
            MyPlaceIQEnergyNumber(
                coordinator, myplaceiq, config_entry, hub_aircon_id, name, spec
            )
            for spec in HUB_NUMBER_SPECS
        )

    entities.extend(
        MyPlaceIQEnergyNumber(
            coordinator, myplaceiq, config_entry, aircon_id,
            aircon_data.get("name", "Aircon"), RUNNING_CURRENT_SPEC
        )
        for aircon_id, aircon_data in aircons.items()
    )
    return entities


class MyPlaceIQEnergyNumber(MyPlaceIQEnergySettingsEntity, NumberEntity):
    # pylint: disable=too-many-instance-attributes
    """A single numeric IQe setting."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, myplaceiq, config_entry, aircon_id, aircon_name, spec):
        # pylint: disable=too-many-arguments, too-many-positional-arguments
        super().__init__(coordinator, myplaceiq, config_entry, aircon_id, aircon_name)
        self._spec = spec
        scope = f"aircon_{aircon_id}" if spec.per_aircon else "hub"
        self._attr_unique_id = f"{config_entry.entry_id}_{scope}_iqe_{spec.key}"
        self._attr_has_entity_name = True
        self._attr_name = f"HVAC IQe {spec.name}"
        self._attr_icon = spec.icon
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = spec.device_class
        self._attr_native_min_value = spec.min_value
        self._attr_native_max_value = spec.max_value
        self._attr_native_step = spec.step

    @property
    def _iqe_managed_visibility(self) -> bool:
        """Only a trigger number is hidden, and only while its own mode is off.

        The other numbers set IQe up, which has to happen before it can be
        turned on, so they are always shown.
        """
        return self._spec.enabled_field is not None

    def _iqe_visible(self, body: dict) -> bool:
        """Show a trigger only while its mode is on."""
        return body.get("energySettings", {}).get(self._spec.enabled_field) is True

    @property
    def native_value(self):
        """Return the current value in Home Assistant units."""
        settings = self._energy_settings()
        if not settings:
            return None
        value = self._spec.read(settings, self._aircon_id)
        return None if value is None else round(value, 2)

    async def async_set_native_value(self, value: float) -> None:
        """Change the setting, leaving every other IQe setting untouched."""
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < self._spec.min_value
            or value > self._spec.max_value
        ):
            raise HomeAssistantError(
                f"{self._spec.name} must be between "
                f"{self._spec.min_value} and {self._spec.max_value}"
            )
        steps = (value - self._spec.min_value) / self._spec.step
        if not math.isclose(steps, round(steps), abs_tol=1e-9):
            raise HomeAssistantError(
                f"{self._spec.name} must use increments of {self._spec.step}"
            )
        await self._async_update_energy_settings(
            lambda settings: self._spec.write(settings, value, self._aircon_id)
        )
