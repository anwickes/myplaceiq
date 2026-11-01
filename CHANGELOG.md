# Changelog

All notable changes to the MyPlaceIQ Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0]
### Added
- QTemp support. A new `switch` entity per aircon (`switch.aircon_hvac_qtemp`) turns QTemp on or off, matching the "Enable QTemp" toggle in the official app. With QTemp on, the controller itself picks the zone that most needs heating or cooling; off returns to manual priority zones. Sent as `SetAirconSettings` with the aircon's complete `airconSettings` object and only `zoneOperation` changed, exactly as the official app does. Only created on controllers that report `zoneOperation`.
- An "Active Control Zone" sensor per aircon, reporting which zone is currently driving the system (from `activeControlZoneName`). Under QTemp this changes automatically; its attributes show the `zone_operation` in force and the `zone_id`. Only created on controllers that report it.
- IQe support (the controller's "run the aircon from excess solar / free electricity hours" feature), on controllers that offer it. The setup wizard's answers are available as entities, written with `SetEnergySettings` using the hub's complete `energySettings` object with only the changed field altered, as the official app does:
  - `switch.aircon_hvac_iqe_auto_cooling` and `switch.aircon_hvac_iqe_auto_heating` - allow IQe to cool or heat automatically.
  - `number` entities for solar panel capacity (kW), inverter capacity (kW), household power use without air conditioning (kW), each aircon's running current (A, converted at the app's fixed 240 V) and the outdoor-temperature triggers for cooling (above) and heating (below). The trigger ranges match the limits the official app enforces; the hub's own limits are not known.
  - `select.aircon_hvac_iqe_free_electricity_hours` - choose None, 11 am to 2 pm, or 12 pm to 3 pm (the periods the app offers). If the hub holds any other schedule the select shows *unknown* and leaves the schedule alone until you pick an option.
  - `switch.aircon_hvac_iqe_active_<weekday>` - the days IQe may run. The hub's day list starts on Sunday even though the app displays Monday first.
  - `sensor.aircon_hvac_iqe_status` (run status, with the planned action, power source, usage mode and active days as attributes) and `sensor.aircon_hvac_iqe_start` / `sensor.aircon_hvac_iqe_stop`, timestamp sensors for when IQe's planned run starts and stops, for use in automations.
  - There is no separate solar switch: choosing "No" to solar panels in the app sets both the solar panel and inverter capacity to 0, so set both numbers to 0 for the same result.
  - Usage mode is shown (as an attribute) but cannot yet be changed from Home Assistant. None of the entities above alter it, the tariffs (other than via the free-hours select) or the days.
- IQe can only be turned on once it has something to run from: either solar panel **and** inverter capacity above 0, **or** free electricity hours (any free period counts). Turning Auto Cooling or Auto Heating on before that fails with a message saying what is missing, and nothing is sent to the controller. Turning them off is always allowed. The same applies in the other direction: while Auto Cooling or Auto Heating is on, a change that would leave IQe with nothing to run from (setting Solar Panel or Inverter Capacity to 0, or choosing None for free electricity hours, when that was the only source) is refused, and you are asked to turn them off first. To switch from one source to the other, set the new one first.
- The entities that show what IQe is doing are hidden in the entity registry while IQe is not running (both modes off), and shown when either mode is enabled: the status sensor and the start/stop timestamp sensors. The cooling and heating trigger numbers are shown only while their own mode is on. Everything used to set IQe up (solar panel, inverter capacity, household power use, running current, free electricity hours and the weekday switches) is always shown, because IQe cannot be turned on until it is set up. All IQe entities always exist, so they never turn `unavailable` after a restart. The integration only hides an entity when IQe switches off and only unhides one it hid itself, so an entity you unhide yourself is not re-hidden while IQe stays off.

### Changed
- **Entity and device naming.** Entities now use Home Assistant's `has_entity_name` convention, so friendly names are built from the device name plus a short entity name, for example "Zone Living HVAC Temperature" instead of `living_temperature`. The climate entity of each zone and aircon is the device's main entity and takes the device name ("Zone Living", "Aircon"). The aircon device is no longer called "Aircon Aircon" when the aircon is named "Aircon". **Upgrading:** existing entity IDs are unchanged, so automations and dashboards keep working, but friendly names change, which affects anything that refers to names (voice assistants, some dashboards). **New installations** get the new entity IDs, e.g. `climate.zone_living`, `binary_sensor.zone_living_hvac_state`, `sensor.aircon_hvac_mode`.
- While QTemp is active the controller disables manual priority selection, so the zone climate entities now hide the `Priority` preset until priority mode is selected again (previously the preset was fixed at startup). The `toggle_priority` buttons are created in either mode, and pressing one while QTemp is active raises a clear error instead of sending a command the controller will not honour.

### Fixed
- The poll debug log no longer hard-codes a single aircon id; it summarises every aircon.

## [1.4.0] - 2026-10-01
### Added
- Fan speed control (`auto`, `1`, `2`, `3`) on the aircon-level climate entity, for both heat and cool mode, via `SetAirconHeatFanSpeed`/`SetAirconCoolFanSpeed` and `SetMyFanHeatingEnabled`/`SetMyFanCoolingEnabled`. `fan_modes` is built from each aircon's own `allowedFanSpeeds` rather than assumed to always be 3. Fan speed is not controllable in dry mode - the hardware doesn't support it there (the official app greys the control out too), so no dry-mode fan command exists.
- `MyPlaceIQ.send_command()` now correlates `GetFullDataEvent` requests with their reply via a client-generated `replyUuid`, matching the behaviour of the official app, instead of assuming the next message on the socket is always the answer.
- A persistent, continuously-read WebSocket connection per config entry, replacing one-shot connect/send/close per command. A background reader task drains every open connection for its whole lifetime, so unsolicited state-change pushes from the hub are now consumed and merged into the cached state as they arrive, instead of only being picked up (if at all) at the next scheduled poll.
- Added functionality to confirm credentials before saving configuration.
- Added branding logos and icons.

### Fixed
- Fixed an issue where rapid, near-simultaneous commands to several entities (e.g. a scene/scene-runner script setting many zones at once) could cause some zones to silently revert to their previous state a few seconds after being set. Root cause: each command previously opened its own short-lived WebSocket connection; a burst of them hitting the hub concurrently caused some to be dropped, and a subsequent poll would then overwrite the optimistic UI state with the hub's unchanged real state. Commands are now serialized onto a single reused connection, which the hub reliably processes one at a time.
- Fixed a related correctness issue introduced by the move to a reused connection: the hub pushes unsolicited partial state deltas to any open connection, independent of polling. Without a dedicated reader loop and request/reply correlation, a routine poll could occasionally consume one of these stale partial pushes instead of its own `GetFullDataEvent` reply, and (because the delta still contained the two top-level keys `_async_update_data` checks for) wholesale-replace the coordinator's entire cached state with just the one or two zones mentioned in that delta. This is now prevented by correlating replies via `replyUuid` and merging (not replacing) any message that isn't a correlated reply.
- The hub closes every WebSocket connection roughly 20 seconds after it is opened, regardless of activity. This is now treated as expected, routine behaviour (reconnect and resync) rather than a connection error.

### Changed
- Post-command polling (`async_request_refresh_after_command`, debounced) is now a backstop for the rare case a push is dropped, rather than the primary way entity state gets confirmed after a `set_*` call - confirmation now normally arrives via the hub's own push, typically in under a second.


## [1.3.0] - 2026-05-24
### Added
- Added control of Priorty zones, and moved sensors to be Binary sensors.


## [1.2.0] - 2026-05-09
### Added
- Changed step size of temperature from 1.0 to 0.5.


## [1.1.0] - 2025-10-17
### Added
- Ensure that climate entities are updated at the same time as the base entities and follow the same polling interval that is defined when configuring the integration.

### Fixed
- Fixed an [issue](https://github.com/anwickes/myplaceiq/issues/13) where the poller was not pulling the correct data from the myplaceiq hub. This subsequently fixes as issue where data is not being updated in home assistant after being modified externally (ie myplaceiq application).


## [1.0.0] - 2025-10-10
### Added
- First official release so contains all added functionality that has been mentioned in previous changelog updates.

### Fixed
- Resolved `AttributeError: 'ConfigEntry' object has no attribute '_update_listener'` in the options flow.
- Improved coordinator to correctly apply the `poll_interval` setting without resetting to default (60 seconds).

### Changed
- Updated `async_config_entry_first_refresh` to `async_refresh` to avoid deprecation warnings in Home Assistant 2025.11.


## [Unreleased] - 2025-10-04
### Added
- Climate entities for zones (e.g., `climate.main_bedroom_climate`) and main system (e.g., `climate.myplaceiq_system`).
- Support for temperature control (`SetZoneHeatTemperature`, `SetAirconHeatTemperature`, etc.) and HVAC modes (`heat`, `cool`, `dry`, `fan`, `off`).
- Integration with thermostat cards for temperature and mode control.
- Optimistic updates for temperature and mode changes.


## [Unreleased] - 2025-10-03
### Added
- Initial support for MyPlaceIQ HVAC hub.
- Sensor entities for zone states (e.g., `sensor.main_bedroom_state`).
- Button entities with optimistic updates (e.g., `button.main_bedroom_toggle`).
- Configuration via UI with host, port, client ID, client secret, and poll interval.
- Options flow to update all configuration fields.

### Changed
- N/A

### Fixed
- N/A
