# Roborock integration for HomeAsssistant

## About this repo
I've bought a Roborock S7 Maxv and hated the fact that I had to use the Roborock App or the previous existing HomeAssistant integration. But not both.

Using the Xiaomi integration there is also a limit to the number of map request which this integration doesn't have

Hope everyone can enjoy this integration along side the Roborock App

[![Buy me a coffee!](https://www.buymeacoffee.com/assets/img/custom_images/black_img.png)](https://www.buymeacoffee.com/humbertogontijo)

---

## Installation

I recommend installing it through [HACS](https://github.com/hacs/integration)

## IMPORTANT
Ensure that your HA instance can listen for device broadcasts on port 58866
Ensure that your HA instance can communicate to device on port 58867

### Installing via HACS
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=humbertogontijo&repository=homeassistant-roborock&category=integration)

or

1. Go to HACS->Integrations
1. Add this repo into your HACS custom repositories
1. Search for Roborock and Download it
1. Restart your HomeAssistant
1. Go to Settings->Devices & Services
1. Shift reload your browser

### Setup the Integration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=roborock)

1. Click Add Integration
1. Search for Roborock
1. Type your username used in the Roborock App and hit submit
1. You will receive an Email with a verification code
1. Type the verification code and hit submit
1. You're all set


---
## Functionality

### Vacuum
- Start the vacuum
- Stop the vacuum
- Pause the vacuum
- Dock the vacuum
- Control vacuum fan speed
- Vacuum battery
- Locate vacuum
- Clean Spot

Additional Vacuum functionality that is supported through services:
- Remote control
- Clean zone
- Go to
- Clean segment
- Set mop mode
- Set mop intensity
- Reset consumables

### Map
There is a map built in to the integration that shows you your most recent/current run of the vacuum. 

### Sensors
- DND start
- DND end
- Last clean start
- Last clean end
- last clean duration
- last clean area
- current error
- current clean duration
- current clean area
- total duration
- total clean area
- total clean count
- total dust collection count
- main brush left
- side brush left
- filter left
- sensor dirty left

### Binary Sensors
- Mop attached
- Water box attached
- Water shortage

## Camera

If your vacuum has a builtin camera, you can use [go2rtc](https://github.com/AlexxIT/go2rtc) made by @AlexxIT. Steps [here](https://github.com/AlexxIT/go2rtc#source-roborock)

---
## Special thanks

Thanks @rovo89 for https://gist.github.com/rovo89/dff47ed19fca0dfdda77503e66c2b7c7
And thanks @PiotrMachowski for https://github.com/PiotrMachowski/Home-Assistant-custom-components-Xiaomi-Cloud-Map-Extractor

---
