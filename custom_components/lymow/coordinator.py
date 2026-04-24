"""DataUpdateCoordinator for Lymow snapshot polling and motion detection."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import io
import logging

import cv2
import numpy as np
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
    STATE_DOCKED,
    STATE_IDLE,
    STATE_MOWING,
    STATE_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)


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
            return LymowData(
                image_bytes=previous_data.image_bytes,
                motion=False,
                docked_guess=previous_data.docked_guess,
                status=STATE_UNKNOWN if self.override_state == STATE_AUTO else self.override_state,
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
        if self.data is not None:
            self.async_set_updated_data(
                LymowData(
                    image_bytes=self.data.image_bytes,
                    motion=self.data.motion,
                    docked_guess=self.data.docked_guess,
                    status=_compute_status(state, self.data.motion, self.data.docked_guess),
                    average_delta=self.data.average_delta,
                )
            )


def _compute_status(override_state: str, motion: bool, docked_guess: bool) -> str:
    if override_state != STATE_AUTO:
        return override_state
    if docked_guess:
        return STATE_DOCKED
    if motion:
        return STATE_MOWING
    return STATE_IDLE


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
    """Detect dock markers as two nearby square contours in the frame."""
    buffer = np.frombuffer(frame, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        return False

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    squares: list[tuple[int, int, int, int]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 1000:
            continue

        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
        if len(approx) != 4:
            continue

        x, y, width, height = cv2.boundingRect(approx)
        aspect_ratio = width / float(height)
        if 0.8 < aspect_ratio < 1.2:
            squares.append((x, y, width, height))

    if len(squares) < 2:
        return False

    for first in range(len(squares)):
        for second in range(first + 1, len(squares)):
            marker_a = squares[first]
            marker_b = squares[second]

            size_ratio = marker_a[2] / marker_b[2]
            if not 0.7 < size_ratio < 1.3:
                continue

            distance = np.linalg.norm(
                np.array([marker_a[0], marker_a[1]]) - np.array([marker_b[0], marker_b[1]])
            )
            if distance < 300:
                return True

    return False
