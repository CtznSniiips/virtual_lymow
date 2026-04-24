# Virtual Lymow Home Assistant Custom Integration

HACS-style custom integration for Virtual Lymow mowers using the hidden RTSP endpoint:

`rtsp://<MOWER_IP>:10022/h264ESVideoTest`

## What it creates

- `sensor.mower_status` (`mowing`, `docked`, `idle`, `unknown`)
- `binary_sensor.mower_motion`
- `binary_sensor.mower_docked_guess`
- `camera.mower_snapshot`
- `select.mower_state` (override/debugging)

> Home Assistant custom integrations can directly provide a `select` entity. If you specifically need an `input_select.mower_state`, mirror this select with a helper + automation in the UI.

## Design

- Native `DataUpdateCoordinator`
- Polling snapshots every _N_ seconds (configurable)
- One-shot `ffmpeg` snapshots (no continuous stream)
- Built-in grayscale frame differencing motion detection
- Pillow-only dock marker detection (no OpenCV/native dependency)

## Install (HACS)

1. Add this repo as a **Custom repository** in HACS (type: **Integration**).
2. Install **Virtual Lymow** from HACS.
3. Restart Home Assistant.
4. Add integration: **Settings → Devices & Services → Add Integration → Virtual Lymow**.
5. Enter mower IP and tuning options.

## Tuning

- **Polling interval**: lower = fresher updates, higher CPU/network usage.
- **Motion threshold**: higher = less sensitive movement detection.
- **Still polls before docked guess**: how many no-motion updates trigger docked guess.
