"""DataUpdateCoordinator for Lymow snapshot polling and motion detection."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import io
import logging
from collections import deque

from PIL import Image, ImageChops, ImageStat

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MOTION_THRESHOLD,
    CONF_MOWER_IP,
    CONF_SCAN_INTERVAL,
    CONF_UNKNOWN_TIMEOUT,
    DEFAULT_MOTION_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNKNOWN_TIMEOUT,
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
        self._unknown_timeout = merged.get(CONF_UNKNOWN_TIMEOUT, DEFAULT_UNKNOWN_TIMEOUT)
        self._rtsp_url = f"rtsp://{self._mower_ip}{RTSP_PATH}"
        self._last_frame: bytes | None = None
        self._last_successful_snapshot_time: datetime | None = None
        self._last_snapshot_error_type: str | None = None
        self._last_snapshot_error_message: str | None = None
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
            if self.override_state != STATE_AUTO:
                status = self.override_state
            else:
                timeout_elapsed = (
                    self._unknown_timeout == 0
                    or self._last_successful_snapshot_time is None
                    or (dt_util.utcnow() - self._last_successful_snapshot_time)
                    >= timedelta(minutes=self._unknown_timeout)
                )
                status = STATE_UNKNOWN if timeout_elapsed else self._last_auto_status
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
        except TimeoutError as err:
            self._set_snapshot_error("timeout", str(err) or "Snapshot timed out after 20 seconds")
            _LOGGER.warning("ffmpeg snapshot timed out for %s", self._rtsp_url)
            return None
        except OSError as err:
            self._set_snapshot_error("execution_error", str(err))
            _LOGGER.error("Unable to execute ffmpeg: %s", err)
            return None

        if process.returncode != 0:
            stderr_text = stderr.decode(errors="ignore").strip()
            error_message = stderr_text or f"ffmpeg exited with return code {process.returncode}"
            self._set_snapshot_error("non_zero_return_code", error_message)
            _LOGGER.debug("ffmpeg failed (%s): %s", process.returncode, stderr_text)
            return None

        if not stdout:
            self._set_snapshot_error("execution_error", "ffmpeg returned no image bytes")
            return None

        self._last_successful_snapshot_time = dt_util.utcnow()
        self._set_snapshot_error(None, None)
        return stdout

    @property
    def last_successful_snapshot_time(self) -> datetime | None:
        """Return the timestamp of the last successful snapshot."""
        return self._last_successful_snapshot_time

    @property
    def last_snapshot_error(self) -> str | None:
        """Return the most recent snapshot error as a compact string."""
        if self._last_snapshot_error_type is None:
            return None
        if self._last_snapshot_error_message:
            return f"{self._last_snapshot_error_type}: {self._last_snapshot_error_message}"
        return self._last_snapshot_error_type

    @property
    def last_snapshot_error_type(self) -> str | None:
        """Return the most recent snapshot error category."""
        return self._last_snapshot_error_type

    @property
    def last_snapshot_error_message(self) -> str | None:
        """Return the most recent snapshot error details."""
        return self._last_snapshot_error_message

    def _set_snapshot_error(self, error_type: str | None, message: str | None) -> None:
        """Store the latest snapshot error details."""
        self._last_snapshot_error_type = error_type
        self._last_snapshot_error_message = message

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

_ADAPTIVE_BLOCK_SIZE = 48   # local block side-length (pixels) for adaptive threshold
_ADAPTIVE_PERCENTILE = 0.82  # within each block, pixels above this percentile → "bright"
_ADAPTIVE_MIN_AREA = 80      # minimum connected-component size to consider


def _detect_dock_markers(frame: bytes) -> bool:
    """Detect dock markers as two similarly sized, horizontally paired bright regions.

    The image is divided into overlapping local blocks and each block is independently
    thresholded at its own Nth-percentile brightness.  This means a pixel is considered
    "bright" only relative to its immediate surroundings, which:

    * works regardless of absolute ambient light level (dim or bright dock),
    * breaks the long-range connectivity path between the dim marker pixels and
      the brighter background at the edges of the frame, and
    * makes no assumption about *where* in the frame the markers appear, so it
      works for any camera angle or mount position.

    After the adaptive binary image is produced, connected-component analysis
    finds candidate bright regions.  ALL region pairs are then tested (not just
    the two largest) for the marker geometry: similar size, horizontal separation,
    and vertical alignment.
    """
    image = Image.open(io.BytesIO(frame)).convert("L")
    image = image.resize((320, 180))
    width, height = image.size
    pixels = image.load()
    if pixels is None:
        return False

    # --- 1. Build adaptive binary image --------------------------------------
    # Each overlapping block votes on whether its pixels are locally bright.
    # Using 50 % overlap (step = block_size // 2) smooths block boundaries.
    binary: list[list[int]] = [[0] * width for _ in range(height)]
    step = _ADAPTIVE_BLOCK_SIZE // 2

    for by in range(0, height, step):
        for bx in range(0, width, step):
            x0, x1 = bx, min(width, bx + _ADAPTIVE_BLOCK_SIZE)
            y0, y1 = by, min(height, by + _ADAPTIVE_BLOCK_SIZE)
            block_vals = sorted(
                pixels[x, y] for y in range(y0, y1) for x in range(x0, x1)
            )
            threshold = block_vals[int(len(block_vals) * _ADAPTIVE_PERCENTILE)]
            for y in range(y0, y1):
                for x in range(x0, x1):
                    if pixels[x, y] > threshold:
                        binary[y][x] = 1

    # --- 2. Flood-fill connected bright regions ------------------------------
    visited: set[tuple[int, int]] = set()
    regions: list[tuple[int, float, float]] = []  # (size, centroid_x, centroid_y)

    for y in range(height):
        for x in range(width):
            if (x, y) in visited or binary[y][x] == 0:
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
                if binary[current_y][current_x] == 0:
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

            if region_size >= _ADAPTIVE_MIN_AREA:
                regions.append((region_size, sum_x / region_size, sum_y / region_size))

    if len(regions) < 2:
        return False

    # --- 3. Find any region pair matching the dock-marker geometry -----------
    # Searching ALL pairs (not just the two largest) means a single giant
    # background blob does not prevent the actual marker regions from matching.
    regions.sort(key=lambda r: r[0], reverse=True)

    for i, (sz1, cx1, cy1) in enumerate(regions):
        for sz2, cx2, cy2 in regions[i + 1:]:
            size_ratio = sz2 / sz1  # sz1 >= sz2 because list is sorted desc
            horizontal_gap = abs(cx1 - cx2)
            vertical_gap = abs(cy1 - cy2)

            if (size_ratio >= 0.5                  # similarly sized
                    and horizontal_gap >= width * 0.1   # far enough apart horizontally
                    and vertical_gap <= height * 0.2):  # close enough vertically
                _LOGGER.debug(
                    "Dock markers found: sizes=%d/%d ratio=%.2f hgap=%.0f vgap=%.0f",
                    sz1, sz2, size_ratio, horizontal_gap, vertical_gap,
                )
                return True

    return False
