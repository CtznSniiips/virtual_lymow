"""Constants for the Lymow integration."""

DOMAIN = "lymow"
PLATFORMS = ["sensor", "binary_sensor", "camera", "select"]

CONF_MOWER_IP = "mower_ip"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MOTION_THRESHOLD = "motion_threshold"

DEFAULT_SCAN_INTERVAL = 180
DEFAULT_MOTION_THRESHOLD = 22.0

RTSP_PATH = ":10022/h264ESVideoTest"

STATE_AUTO = "Auto"
STATE_MOWING = "Mowing"
STATE_DOCKED = "Docked"
STATE_IDLE = "Idle"
STATE_UNKNOWN = "Unknown"
STATE_CHARGING = "Charging"

OVERRIDE_OPTIONS = [STATE_AUTO, STATE_MOWING, STATE_DOCKED, STATE_IDLE, STATE_UNKNOWN, STATE_CHARGING]
