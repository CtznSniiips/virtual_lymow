"""Constants for the Virtual Lymow integration."""

from homeassistant.const import Platform

DOMAIN = "virtual_lymow"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CAMERA, Platform.SELECT]

CONF_MOWER_NAME = "mower_name"
CONF_MOWER_IP = "mower_ip"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MOTION_THRESHOLD = "motion_threshold"
CONF_UNKNOWN_TIMEOUT = "unknown_timeout"

DEFAULT_SCAN_INTERVAL = 180
DEFAULT_MOTION_THRESHOLD = 22.0
DEFAULT_UNKNOWN_TIMEOUT = 10

RTSP_PATH = ":10022/h264ESVideoTest"

STATE_AUTO = "Auto"
STATE_MOWING = "Mowing"
STATE_DOCKED = "Docked"
STATE_IDLE = "Idle"
STATE_UNKNOWN = "Unknown"
STATE_CHARGING = "Charging"

OVERRIDE_OPTIONS = [STATE_AUTO, STATE_MOWING, STATE_DOCKED, STATE_IDLE, STATE_UNKNOWN, STATE_CHARGING]
