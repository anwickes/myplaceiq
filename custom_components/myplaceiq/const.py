DOMAIN = "myplaceiq"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_POLL_INTERVAL = "poll_interval"


def aircon_device_name(name: str) -> str:
    """Return the device name for an aircon.

    Most controllers call the aircon "Aircon", which would otherwise give a
    device (and every entity name built from it) called "Aircon Aircon", so
    only add the "Aircon" prefix when the name does not already start with it.
    """
    name = (name or "Aircon").strip()
    return name if name.lower().startswith("aircon") else f"Aircon {name}"


def zone_device_name(name: str) -> str:
    """Return the device name for a zone."""
    return f"Zone {name}"
