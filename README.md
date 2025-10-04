# MyPlaceIQ Home Assistant Integration
![MyPlaceIQ Logo](custom_components/myplaceiq/images/logo.png)

The MyPlaceIQ integration allows Home Assistant to communicate with a MyPlaceIQ HVAC hub, enabling control and monitoring of heating, ventilation, and air conditioning systems. This integration connects to the hub via a WebSocket connection, providing real-time state updates and control capabilities for devices like Rinnai HVAC units.

## Features
- **Sensors**: Monitor the state of HVAC zones (e.g., `sensor.rumpus_state`, `sensor.main_bedroom_state`).
- **Buttons**: Control zones with toggle buttons (e.g., `button.rumpus_toggle`, `button.main_bedroom_toggle`) with optimistic updates for instant feedback.
- **Configuration**: Set up via the Home Assistant UI with support for host, port, client ID, client secret, and polling interval.
- **Options Flow**: Update all configuration fields (host, port, client ID, client secret, polling interval) via the integration settings.

## Thermostat Integration
- **Climate Entities**: Use `climate` entities with Home Assistant’s built-in thermostat card or `simple-thermostat` (via HACS) to control temperatures and modes.
  - Zones (e.g., `climate.main_bedroom_climate`): Control temperature (16–30°C) and on/off state. Zones inherit the system’s mode (`heat`, `cool`, `dry`, `fan`).
  - Main System (e.g., `climate.myplaceiq_system`): Control temperature and modes (`heat`, `cool`, `dry`, `fan`, `off`).
- **Lovelace Configuration**:
  ```yaml
  type: thermostat
  entity: climate.main_bedroom_climate

## Installation

### Via HACS (Recommended)
1. Ensure [HACS](https://hacs.xyz/) is installed in Home Assistant.
2. Go to **HACS > Integrations > Explore & Download Repositories**.
3. Search for "MyPlaceIQ" or add the custom repository: `https://github.com/anwickes/myplaceiq`.
4. Click **Download** and follow the prompts to install.
5. Restart Home Assistant.
6. Go to **Settings > Devices & Services > Add Integration > MyPlaceIQ** and configure with your hub's details.

### Manual Installation
1. Copy the `custom_components/myplaceiq/` folder to your Home Assistant configuration directory (`/config/custom_components/myplaceiq/`).
2. Restart Home Assistant.
3. Go to **Settings > Devices & Services > Add Integration > MyPlaceIQ** and configure.

## Configuration
1. In Home Assistant, go to **Settings > Devices & Services > Add Integration**.
2. Search for "MyPlaceIQ" and select it.
3. Enter:
   - **Host**: The IP address of your MyPlaceIQ hub (e.g., `192.168.1.171`).
   - **Port**: The WebSocket port (default: `8086`).
   - **Client ID**: Your MyPlaceIQ client ID.
   - **Client Secret**: Your MyPlaceIQ client secret.
   - **Poll Interval**: How often to fetch updates (default: 60 seconds, range: 10–300 seconds).
4. Submit to add the integration.
5. Use the **Options** flow (cog icon) to update settings later.

## Entities
- **Sensors**: Display HVAC zone states (e.g., `on`, `off`).
  - Example: `sensor.main_bedroom_state`
- **Buttons**: Toggle HVAC zones with optimistic updates.
  - Example: `button.main_bedroom_toggle`

## Notes
### Host & Credential Retrieval
As of the time of writing (3rd Oct, 2025), the method of obtaining the client id and password is a little tricky. I was able to retrieve them by setting up port mirroring on a switch that I have on my network. I mirrored packets received and transmitted by the myplaceiq hub to another PC that was monitoring with Wireshark. After connecting to the hub via the myplaceiq app on my phone (any device would be fine), I could see a packet that was sent which contained the client id and secret in plaintext. I have attempted to use a mitmproxy (like Charles proxy, mitmproxy etc) to retrieve this information but haven't managed to work it out yet.

### IP Address vs. DNS
- Home Assistant does not support mDNS (multicast DNS) for resolving hostnames. You must use the hub’s static IP address (e.g., `192.168.1.x`) in the configuration.
- To find the IP address of your myplaceiq hub, check your router’s DHCP client list or use a network scanner. Ensure the hub has a static IP to prevent changes during DHCP lease renewals.

## Requirements
- Home Assistant 2023.9 or later.

## Development
- **Issues**: Report bugs or feature requests at [GitHub Issues](https://github.com/anwickes/myplaceiq/issues).
- **Source**: [https://github.com/anwickes/myplaceiq](https://github.com/anwickes/myplaceiq).
- **License**: MIT.

## Screenshots
TBA

## Acknowledgments
Developed by @anwickes for the Home Assistant community.

See Sponsorships section below if you would like to support this integration by buying me a coffee.
