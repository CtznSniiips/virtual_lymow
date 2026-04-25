"""DataUpdateCoordinator for Lymow snapshot polling and motion detection."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import io
import logging
from collections import deque

from PIL import Image, ImageChops, ImageStat

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_MOTION_THRESHOLD,
    CONF_MOWER_IP,
    CONF_SCAN_INTERVAL,
    DEFAULT_MOTION_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OVERRIDE_OPTIONS,
    RTSP_PATH,
    STATE_AUTO,
    STATE_CHARGING,
    STATE_DOCKED,
    STATE_IDLE,
    STATE_MOWING,
    STATE_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)
_STATIONARY_STATES = {STATE_DOCKED, STATE_CHARGING}


@dataclass
class LymowData:
    """Coordinator data snapshot."""

    image_bytes: bytes | None
    motion: bool
    docked_guess: bool
    status: str
    average_delta: float | None


class LymowCoordinator(DataUpdateCoordinator[LymowData]):
    """Coordinate updates for Lymow entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        merged = {**entry.data, **entry.options}
        self._mower_ip = merged[CONF_MOWER_IP]
        self._scan_interval = merged.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self._motion_threshold = merged.get(CONF_MOTION_THRESHOLD, DEFAULT_MOTION_THRESHOLD)
        self._rtsp_url = f"rtsp://{self._mower_ip}{RTSP_PATH}"
        self._last_frame: bytes | None = None
        self.override_state = STATE_AUTO
        self._last_auto_status: str = STATE_UNKNOWN

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=self._scan_interval),
        )

    async def _async_update_data(self) -> LymowData:
        frame = await self._capture_snapshot()
        if frame is None:
            previous_data = self.data or self._fallback_data()
            status = STATE_UNKNOWN if self.override_state == STATE_AUTO else self.override_state
            if self.override_state == STATE_AUTO:
                status = _guard_stationary_to_idle(self._last_auto_status, status)
                self._last_auto_status = status
            return LymowData(
                image_bytes=previous_data.image_bytes,
                motion=False,
                docked_guess=previous_data.docked_guess,
                status=status,
                average_delta=None,
            )

        avg_delta = None
        motion = False
        if self._last_frame is not None:
            motion, avg_delta = await asyncio.to_thread(
                _detect_motion,
                self._last_frame,
                frame,
                self._motion_threshold,
            )

        docked_guess = await asyncio.to_thread(_detect_dock_markers, frame)
        self._last_frame = frame

        status = _compute_status(self.override_state, motion, docked_guess)
        if self.override_state == STATE_AUTO:
            status = _guard_stationary_to_idle(self._last_auto_status, status)
            self._last_auto_status = status

        return LymowData(
            image_bytes=frame,
            motion=motion,
            docked_guess=docked_guess,
            status=status,
            average_delta=avg_delta,
        )

    def _fallback_data(self) -> LymowData:
        """Return safe defaults when no prior coordinator data exists."""
        return LymowData(
            image_bytes=None,
            motion=False,
            docked_guess=False,
            status=STATE_UNKNOWN if self.override_state == STATE_AUTO else self.override_state,
            average_delta=None,
        )

    async def _capture_snapshot(self) -> bytes | None:
        """Capture one frame from RTSP using ffmpeg."""
        cmd = [
            "ffmpeg",
            "-rtsp_transport",
            "tcp",
            "-i",
            self._rtsp_url,
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-",
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=20)
        except TimeoutError:
            _LOGGER.warning("ffmpeg snapshot timed out for %s", self._rtsp_url)
            return None
        except OSError as err:
            _LOGGER.error("Unable to execute ffmpeg: %s", err)
            return None

        if process.returncode != 0 or not stdout:
            _LOGGER.debug("ffmpeg failed (%s): %s", process.returncode, stderr.decode(errors="ignore"))
            return None

        return stdout

    async def async_set_override_state(self, state: str) -> None:
        """Set override state from select entity."""
        if state not in OVERRIDE_OPTIONS:
            return
        self.override_state = state
        if state == STATE_AUTO and self.data is not None:
            self._last_auto_status = self.data.status
        if self.data is not None:
            status = _compute_status(state, self.data.motion, self.data.docked_guess)
            if state == STATE_AUTO:
                status = _guard_stationary_to_idle(self._last_auto_status, status)
            self.async_set_updated_data(
                LymowData(
                    image_bytes=self.data.image_bytes,
                    motion=self.data.motion,
                    docked_guess=self.data.docked_guess,
                    status=status,
                    average_delta=self.data.average_delta,
                )
            )


def _compute_status(override_state: str, motion: bool, docked_guess: bool) -> str:
    """Compute displayed mower status from override + inferred state."""
    if override_state != STATE_AUTO:
        return override_state
    if docked_guess:
        return STATE_DOCKED
    if motion:
        return STATE_MOWING
    return STATE_IDLE


def _guard_stationary_to_idle(previous: str, new: str) -> str:
    """Block a direct Docked/Charging → Idle transition; Mowing must occur first."""
    if previous in _STATIONARY_STATES and new == STATE_IDLE:
        return previous
    return new


def _detect_motion(previous: bytes, current: bytes, threshold: float) -> tuple[bool, float]:
    """Return whether two snapshots indicate meaningful motion."""
    prev_img = Image.open(io.BytesIO(previous)).convert("L")
    curr_img = Image.open(io.BytesIO(current)).convert("L")

    if prev_img.size != curr_img.size:
        curr_img = curr_img.resize(prev_img.size)

    diff = ImageChops.difference(prev_img, curr_img)
    stat = ImageStat.Stat(diff)
    avg_delta = float(stat.mean[0])
    return avg_delta >= threshold, avg_delta

def _detect_dock_markers(frame: bytes) -> bool:
    """Detect dock markers as two similarly sized, horizontally paired bright regions."""
    image = Image.open(io.BytesIO(frame)).convert("L")
    image = image.resize((320, 180))

    width, height = image.size
    pixels = image.load()
    if pixels is None:
        return False

    visited: set[tuple[int, int]] = set()
    regions: list[tuple[int, float, float]] = []  # (size, centroid_x, centroid_y)
    bright_threshold = 180
    minimum_region_area = 200

    for y in range(height):
        for x in range(width):
            if (x, y) in visited or pixels[x, y] <= bright_threshold:
                continue

            stack: deque[tuple[int, int]] = deque([(x, y)])
            region_size = 0
            sum_x = 0
            sum_y = 0

            while stack:
                current_x, current_y = stack.pop()
                if (current_x, current_y) in visited:
                    continue
                if current_x < 0 or current_y < 0 or current_x >= width or current_y >= height:
                    continue
                if pixels[current_x, current_y] <= bright_threshold:
                    continue

                visited.add((current_x, current_y))
                region_size += 1
                sum_x += current_x
                sum_y += current_y

                for delta_x in (-1, 0, 1):
                    for delta_y in (-1, 0, 1):
                        if delta_x == 0 and delta_y == 0:
                            continue
                        stack.append((current_x + delta_x, current_y + delta_y))

            if region_size >= minimum_region_area:
                centroid_x = sum_x / region_size
                centroid_y = sum_y / region_size
                regions.append((region_size, centroid_x, centroid_y))

    if len(regions) < 2:
        return False

    regions.sort(key=lambda r: r[0], reverse=True)
    largest_size, lx, ly = regions[0]
    second_size, sx, sy = regions[1]

    if largest_size == 0:
        return False

    # Regions must be similarly sized
    if second_size < largest_size * 0.75:
        return False

    # Regions must be side-by-side: separated horizontally but at similar heights
    horizontal_gap = abs(lx - sx)
    vertical_gap = abs(ly - sy)
    if horizontal_gap < width * 0.1:   # not far enough apart horizontally
        return False
    if vertical_gap > height * 0.2:    # too far apart vertically
        return False

    return True
