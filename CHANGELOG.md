# Changelog

All notable changes to the MyPlaceIQ Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## [Unreleased] - 2025-10-04
### Added
- Climate entities for zones (e.g., `climate.main_bedroom_climate`) and main system (e.g., `climate.myplaceiq_system`).
- Support for temperature control (`SetZoneHeatTemperature`, `SetAirconHeatTemperature`, etc.) and HVAC modes (`heat`, `cool`, `dry`, `fan`, `off`).
- Integration with thermostat cards for temperature and mode control.
- Optimistic updates for temperature and mode changes.