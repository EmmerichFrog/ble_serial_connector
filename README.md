# DESCRIPTION
This script will connect to the flipper via bluetooth and pull data from an Home Assistant instance and send it via bluetooth serial.

# HOW TO USE
rename the config_example.json to config.json and edit it:
- "host" should point to the HA endpoint,
- "token" should be your HA login token,
- add as many kv pairs as needed, where the key is the entity_id on HA and the value is the custom name used on the request/response from/to the Flipper.
