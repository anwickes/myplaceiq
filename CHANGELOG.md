# Changelog

All notable changes to the MyPlaceIQ Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2026-10-01
### Added
- Fan speed control (`auto`, `1`, `2`, `3`) on the aircon-level climate entity, for both heat and cool mode, via `SetAirconHeatFanSpeed`/`SetAirconCoolFanSpeed` and `SetMyFanHeatingEnabled`/`SetMyFanCoolingEnabled`. `fan_modes` is built from each aircon's own `allowedFanSpeeds` rather than assumed to always be 3. Fan speed is not controllable in dry mode - the hardware doesn't support it there (the official app greys the control out too), so no dry-mode fan command exists.
- `MyPlaceIQ.send_command()` now correlates `GetFullDataEvent` requests with their reply via a client-generated `replyUuid`, matching the behaviour of the official app, instead of assuming the next message on the socket is always the answer.
- A persistent, continuously-read WebSocket connection per config entry, replacing one-shot connect/send/close per command. A background reader task drains every open connection for its whole lifetime, so unsolicited state-change pushes from the hub are now consumed and merged into the cached state as they arrive, instead of only being picked up (if at all) at the next scheduled poll.

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
