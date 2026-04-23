"""Constants for the Lymow integration."""

DOMAIN = "lymow"
PLATFORMS = ["sensor", "binary_sensor", "camera", "select"]

CONF_MOWER_IP = "mower_ip"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MOTION_THRESHOLD = "motion_threshold"
CONF_DOCKED_STILL_POLLS = "docked_still_polls"

DEFAULT_SCAN_INTERVAL = 180
DEFAULT_MOTION_THRESHOLD = 12.0
DEFAULT_DOCKED_STILL_POLLS = 5

RTSP_PATH = ":10022/h264ESVideoTest"

STATE_AUTO = "auto"
STATE_MOWING = "mowing"
STATE_DOCKED = "docked"
STATE_IDLE = "idle"
STATE_UNKNOWN = "unknown"

OVERRIDE_OPTIONS = [STATE_AUTO, STATE_MOWING, STATE_DOCKED, STATE_IDLE, STATE_UNKNOWN]
