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
DISCLAIMER: There are probably many ways to do this, all differing from platform to platform. This is the method that I used with my macbook air (silicon).

- Download Wireshark (https://www.wireshark.org/download.html) and BlueStacks Air (https://www.bluestacks.com/mac). Install both.
- Launch Wireshark, choose the appropriate network adapter and filter traffic to/from your MyPlaceIQ hub's ip address using the following filter: "ip.addr==x.x.x.x".
- Launch BlueStacks and click the Home button ("House" symbol at the top of screen). Open the "System Apps" folder and open PlayStore. Login with your Google details. After logging in, search and install "MyPlaceIQ".
- After opening the MyPlaceIQ app, click through the wizard and setup as you would a new device. This includes pairing with the hub etc. 
- Once paired and confirming that you can control the unit, close the app and open Wireshark.
- Confirm that Wireshark is currently recording and filtered to your MyPlaceIQ hub's IP address.
- Using BlueStacks, open up the MyPlaceIQ app and after it successfully logs in, press the stop button in Wireshark to pause recording.
- Look through the packets that have been sent to and from your MyPlaceIQ hub and you should see a "HTTP" packet sent from your BlueStacks device to your MyPlaceIQ hub. Click into this packet and you should see a payload that contains both the "client_id" and "password" that is being issued to your hub. 
- Make a note of these credentials as this is what you will be using when configuring this Home Assistant component.

### IP Address vs. DNS
- Home Assistant does not support mDNS (multicast DNS) for resolving hostnames. You must use the hub’s static IP address (e.g., `192.168.1.x`) in the configuration.
- To find the IP address of your MyPlaceIQ hub, check your router’s DHCP client list or use a network scanner. Ensure the hub has a static IP to prevent changes during DHCP lease renewals.

## Requirements
- Home Assistant 2023.9 or later.

## Development
- **Issues**: Report bugs or feature requests at [GitHub Issues](https://github.com/anwickes/myplaceiq/issues).
- **Source**: [https://github.com/anwickes/myplaceiq](https://github.com/anwickes/myplaceiq).
- **License**: MIT.

## Screenshots

<img width="826" height="670" alt="image" src="https://github.com/user-attachments/assets/71fb43f2-73e5-41f8-81e1-755427b42681" />
<img width="273" height="651" alt="image" src="https://github.com/user-attachments/assets/81cc9098-bda0-4972-9051-c9303d306bc7" />
<img width="266" height="495" alt="image" src="https://github.com/user-attachments/assets/687f14ea-9135-4d6a-b2db-77130b634964" />
<img width="1104" height="462" alt="image" src="https://github.com/user-attachments/assets/d2d556ca-ddbb-491f-8910-f85f812bd9a9" />





## Acknowledgments
Developed by @anwickes for the Home Assistant community.

See Sponsorship section if you would like to support this integration by buying me a coffee.
