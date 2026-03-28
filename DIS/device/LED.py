# device/LED.py (OUR TSI)
from machine import Pin
import neopixel
import time

def clamp(x, lo, hi):
    return max(lo, min(x, hi))

class TargetSpeedIndicator:
    """
    Owns the NeoPixel strip and updates it based on:
      current_speed (mph), target_speed (mph), race_mode (bool), smart_cruise (bool)
    """

    # --- LED layout constants (your original mapping) ---
    CENTER_NORMAL_L = 6
    CENTER_NORMAL_R = 7

    CENTER_SLOW_L = 9
    CENTER_SLOW_R = 10

    CENTER_FAST_L = 3
    CENTER_FAST_R = 4

    CENTER_COLOR = (10, 10, 10)        # dim white center indicator
    SMART_CRUISE_COLOR = (255, 0, 255) # purple

    DEADBAND = 0.1
    FULL_SCALE = 3.0  # mph

    # --- Panic Blink Settings ---
    BLINK_THRESHOLD_ON = 3.0     # mph behind to start blinking
    BLINK_THRESHOLD_OFF = 2.5    # mph behind to stop blinking (hysteresis)
    BLINK_DELAY_MS = 500         # must be behind this long to activate

    BLINK_PERIOD_MS = 500        # normal blink speed (2 Hz)
    FAST_BLINK_THRESHOLD = 5.0   # mph behind to blink faster
    FAST_BLINK_PERIOD_MS = 300   # faster blink speed (~3.3 Hz)

    BLINK_COLOR = (255, 0, 0)    # red

    PALETTE = [
        (255, 0, 0),     # 0
        (255, 80, 0),    # 1
        (255, 160, 0),   # 2
        (255, 255, 0),   # 3
        (160, 255, 0),   # 4
        (80, 255, 0),    # 5
        (0, 255, 0),     # 6
        (0, 255, 80),    # 7
        (0, 255, 160),   # 8
        (0, 255, 255),   # 9
        (0, 160, 255),   # 10
        (0, 80, 255),    # 11
        (0, 0, 255),     # 12
        (80, 0, 255),    # 13
    ]

    def __init__(self, data_pin=16, num_leds=14):
        self.num_leds = num_leds
        self.np = neopixel.NeoPixel(Pin(data_pin), num_leds)

        # Pre-allocated pixel buffer to avoid per-loop allocations
        self._pixels = [(0, 0, 0)] * num_leds

        # Cache last frame to minimize np.write() calls
        self._last_pixels = [(0, 0, 0)] * num_leds
        self._last_race_mode = None

        # Panic blink state
        self._panic_active = False
        self._panic_timer_start = None
        self._blink_state = True
        self._last_blink_ms = time.ticks_ms()

        # Showroom animation state
        self._showroom_step = 0
        self._showroom_last_ms = 0

        # Start off
        self.off(force_write=True)

    def _clear_pixels(self):
        for i in range(self.num_leds):
            self._pixels[i] = (0, 0, 0)

    def off(self, force_write=False):
        self._clear_pixels()
        self._apply(self._pixels, force_write=force_write)

    def update(self, vehicle):
        current_speed = vehicle.motor_mph
        target_speed = vehicle.target_mph
        race_mode = (vehicle.state == "RACE" or vehicle.state == "COMP")
        smart_cruise = vehicle.smart_cruise

        # 1 Race mode OFF => all off (only write if changed)
        if not race_mode:
            self.off(force_write=(self._last_race_mode is True))
            self._last_race_mode = False
            return

        self._last_race_mode = True

        # 2 Clear pre-allocated pixel buffer
        self._clear_pixels()
        pixels = self._pixels

        error = current_speed - target_speed  # 3 + fast, - slow

        # 4 Decide center indicator position
        if error < -self.FULL_SCALE:
            cL, cR = self.CENTER_SLOW_L, self.CENTER_SLOW_R
        elif error > self.FULL_SCALE:
            cL, cR = self.CENTER_FAST_L, self.CENTER_FAST_R
        else:
            cL, cR = self.CENTER_NORMAL_L, self.CENTER_NORMAL_R

        # 5 Draw center indicator
        pixels[cL] = self.CENTER_COLOR
        pixels[cR] = self.CENTER_COLOR

        # 6 Deadband: dot becomes both center LEDs
        if abs(error) <= self.DEADBAND:
            dot_color = self.SMART_CRUISE_COLOR if smart_cruise else self.PALETTE[cL]
            pixels[cL] = dot_color
            pixels[cR] = dot_color
            self._apply(pixels)
            return

        # 7 Dot position
        if error < -self.FULL_SCALE:
            dot = 0
        elif error > self.FULL_SCALE:
            dot = self.num_leds - 1
        else:
            half = (self.num_leds - 1) / 2.0  # 6.5 for 14 LEDs
            dot_float = (error / self.FULL_SCALE) * half + half

            # bias to match your old “slow side” behavior
            if error < 0:
                dot = int(dot_float + 0.8)
            else:
                dot = int(dot_float + 0.5)

            dot = clamp(dot, 0, self.num_leds - 1)

        dot_color = self.SMART_CRUISE_COLOR if smart_cruise else self.PALETTE[dot]

        # -------------------------------------------------
        # PANIC BLINK LOGIC (far behind target)
        # -------------------------------------------------
        behind_amount = -error  # positive when slow
        now = time.ticks_ms()

        # Activate after delay
        if (behind_amount >= self.BLINK_THRESHOLD_ON) and (not smart_cruise):
            if self._panic_timer_start is None:
                self._panic_timer_start = now
            elif time.ticks_diff(now, self._panic_timer_start) >= self.BLINK_DELAY_MS:
                self._panic_active = True
        else:
            self._panic_timer_start = None

        # Deactivate with hysteresis
        if self._panic_active and (behind_amount <= self.BLINK_THRESHOLD_OFF):
            self._panic_active = False

        # Blink behavior (normal blink vs fast blink)
        if self._panic_active:
            period_ms = self.FAST_BLINK_PERIOD_MS if (behind_amount >= self.FAST_BLINK_THRESHOLD) else self.BLINK_PERIOD_MS

            if time.ticks_diff(now, self._last_blink_ms) >= (period_ms // 2):
                self._blink_state = not self._blink_state
                self._last_blink_ms = now

            if self._blink_state:
                pixels[dot] = self.BLINK_COLOR
            # else: leave dot off (blink off phase)
        else:
            pixels[dot] = dot_color

        self._apply(pixels)

    def showroom_update(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._showroom_last_ms) >= 30:
            self._showroom_step = (self._showroom_step + 1) % 42
            self._showroom_last_ms = now

        step = self._showroom_step
        pixels = self._pixels
        for i in range(self.num_leds):
            idx = (step + i * 3) % 42
            if idx < 14:
                r = 255 - idx * 18
                g = idx * 18
                b = 0
            elif idx < 28:
                j = idx - 14
                r = 0
                g = 255 - j * 18
                b = j * 18
            else:
                j = idx - 28
                r = j * 18
                g = 0
                b = 255 - j * 18
            pixels[i] = (r >> 2, g >> 2, b >> 2)
        self._apply(pixels)

    def showroom_off(self):
        self._showroom_step = 0
        self.off(force_write=True)

    def _apply(self, pixels, force_write=False):
        # Only write if something changed
        if (not force_write) and (pixels == self._last_pixels):
            return

        # MIRRORED OUTPUT 
        for i, col in enumerate(pixels):
            mirrored_index = self.num_leds - 1 - i
            self.np[mirrored_index] = col

        self.np.write()
        self._last_pixels = list(pixels)