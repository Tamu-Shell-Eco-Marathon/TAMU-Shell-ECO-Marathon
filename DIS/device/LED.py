# device/LED.py (OUR TSI)
from machine import Pin
import neopixel

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


        # It is now connected to the physical LEDs.
    def __init__(self, data_pin=16, num_leds=14):
        self.num_leds = num_leds
        self.np = neopixel.NeoPixel(Pin(data_pin), num_leds)

        # Cache last frame to minimize np.write() calls
        self._last_pixels = [(0, 0, 0)] * num_leds
        self._last_race_mode = None

        # Start off
        self.off(force_write=True)

    def off(self, force_write=False):
        pixels = [(0, 0, 0)] * self.num_leds
        self._apply(pixels, force_write=force_write)

    # def update(self, current_speed, target_speed, race_mode, smart_cruise):
    def update(self, vehicle):
        current_speed = vehicle.motor_mph
        target_speed = vehicle.target_mph
        race_mode = (vehicle.state == "RACE")
        smart_cruise = vehicle.smart_cruise

        #1 Race mode OFF => all off (only write if changed)
        if not race_mode:
            self.off(force_write=(self._last_race_mode is True))
            self._last_race_mode = False
            return

        self._last_race_mode = True

        #2 Build a fresh frame in a Python list first
        pixels = [(0, 0, 0)] * self.num_leds

        error = current_speed - target_speed  #3 + fast, - slow

        #4 Decide center indicator position
        if error < -self.FULL_SCALE:
            cL, cR = self.CENTER_SLOW_L, self.CENTER_SLOW_R
        elif error > self.FULL_SCALE:
            cL, cR = self.CENTER_FAST_L, self.CENTER_FAST_R
        else:
            cL, cR = self.CENTER_NORMAL_L, self.CENTER_NORMAL_R

        #5 Draw center indicator
        pixels[cL] = self.CENTER_COLOR
        pixels[cR] = self.CENTER_COLOR

        #6 Deadband: dot becomes both center LEDs
        if abs(error) <= self.DEADBAND:
            dot_color = self.SMART_CRUISE_COLOR if smart_cruise else self.PALETTE[cL]
            pixels[cL] = dot_color
            pixels[cR] = dot_color
            self._apply(pixels)
            return

        #7 Dot position
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
        pixels[dot] = dot_color

        self._apply(pixels)

    def _apply(self, pixels, force_write=False):
        # Only write if something changed
        if (not force_write) and (pixels == self._last_pixels):
            return

        for i, col in enumerate(pixels):
            self.np[i] = col
        self.np.write()

        self._last_pixels = pixels
