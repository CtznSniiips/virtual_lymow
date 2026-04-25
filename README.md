# Virtual Lymow Home Assistant Custom Integration

<p align="center">
<img width="256px" src="https://github.com/CtznSniiips/virtual-lymow/blob/main/custom_components/virtual-lymow/brand/logo.png?raw=true" alt="Virtual Lymow"></img>
</p>

HACS-style custom integration for Virtual Lymow mowers using the hidden RTSP endpoint:

`rtsp://<MOWER_IP>:10022/h264ESVideoTest`

## What it creates

- `sensor.mower_status` (`Mowing`, `Docked`, `Idle`, `Unknown`, `Charging`)
- `binary_sensor.mower_motion`
- `binary_sensor.mower_docked_guess`
- `camera.mower_snapshot`
- `select.mower_state` (`Mowing`, `Docked`, `Idle`, `Unknown`, `Charging`, `Auto`) for override/debugging

`Charging` is a manual status override. You can set it from automations (for example, when a smart plug detects high charging power draw), then set state back to `Auto` when charging ends.

## How it works
The integration doesn't use any official Lymow API — instead it taps into a hidden video stream (RTSP) that the mower broadcasts over your local network. Every polling interval it grabs a single still frame from that stream using ffmpeg, then uses that image to figure out what the mower is up to.

**Motion detection** works by comparing the latest frame to the previous one. If enough pixels have changed between the two shots, the mower is considered to be moving. You can tune how sensitive this is with the motion threshold setting.

**Dock detection** works by looking for the dock's charging markers in the image pulled from the video stream. The dock has two bright regions that appear side-by-side at a similar height — the integration scans the frame for exactly that pattern. If it finds it, the mower is assumed to be sitting in the dock.

Status is then computed from those two signals:

 - Dock markers visible → Docked
 - No dock markers, but motion detected → Mowing
 - No dock markers, no motion → Idle
 - Camera unreachable → Unknown

**Manual override** lets you force the status to any value from the UI or an automation, which is useful for states the camera can't detect on its own — like Charging. When you're done, set it back to Auto and the integration resumes making its own decisions.

**Stationary state protection** prevents the status from jumping straight from Docked or Charging to Idle. Since a mower at rest in the dock and a mower sitting idle in a field could look the same to the camera (no motion, no dock markers visible, eg. at night), the integration won't call it Idle until it has first seen the mower actually Mowing — confirming it left its stationary position before coming to a stop.

## Install (HACS)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=CtznSniiips&repository=virtual-lymow&category=integration)

1. Add this repo as a **Custom repository** in HACS (type: **Integration**).
2. Install **Virtual Lymow** from HACS.
3. Restart Home Assistant.
4. Add integration: **Settings → Devices & Services → Add Integration → Virtual Lymow**.
5. Enter mower IP and tuning options.

## Tuning

- **Polling interval**: lower = fresher updates, higher Lymow battery drain. (default `180` seconds)
- **Motion threshold**: higher = less sensitive movement detection. (default `22`)

## Design

- Native `DataUpdateCoordinator`
- Polling snapshots every _N_ seconds (configurable)
- One-shot `ffmpeg` snapshots (no continuous stream)
- Built-in grayscale frame differencing motion detection
- Pillow-only dock marker detection (no OpenCV/native dependency)
