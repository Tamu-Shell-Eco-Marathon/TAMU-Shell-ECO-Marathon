# This class contains all of the states of the vehicle for all of the "signals" that we care about.
# It includes measured signals (from the motor controller) as well as derived signals

import utime as time
import math

# ---- Competition Race Parameters ----
GOAL_DISTANCE_MI = 9.56              # Total race distance (miles)
GOAL_TIME_SEC = 35 * 60              # Total race time (seconds)
COMP_NUM_LAPS = 4                    # Number of laps in the race

# ---- Lap Calibration Distances (miles, cumulative) ----
# Measured during practice session - UPDATE BEFORE COMPETITION
COMP_LAP_1_DISTANCE = 2.39           # Cumulative distance at end of lap 1
COMP_LAP_2_DISTANCE = 4.78           # Cumulative distance at end of lap 2
COMP_LAP_3_DISTANCE = 7.17           # Cumulative distance at end of lap 3
COMP_LAP_DISTANCES = [COMP_LAP_1_DISTANCE, COMP_LAP_2_DISTANCE, COMP_LAP_3_DISTANCE]

# ---- Calibration Settings ----
COMP_ADJUST_TICKS_PER_MILE = False   # Set True to also recalculate TICKS_PER_MILE on calibration
COMP_CALIBRATION_MARGIN = 0.10       # 10% margin for lap distance sanity check

# ---- Screen Scheduler Timing ----
COMP_SPEEDOMETER_MIN_SEC = 30        # Minimum seconds on speedometer between other screens
COMP_SCREEN_DISPLAY_SEC = 5          # How long each non-speedometer screen shows
COMP_SCREEN_INVERT_SEC = 1           # How long to invert display on screen change

# ---- Timer Screen Intervals ----
COMP_TIMER_INTERVAL_SEC = 300        # Show timer every 5 minutes (300s)
COMP_TIMER_URGENT_THRESHOLD = 300    # When remaining time < 5 min, increase frequency
COMP_TIMER_URGENT_INTERVAL_SEC = 60  # Show timer every 1 minute when urgent

# ---- Odometer Screen Intervals ----
COMP_ODOMETER_INTERVAL_MI = 1.0      # Show odometer every 1 mile

# ---- Target Speed Screen Intervals ----
COMP_TARGET_INTERVAL_NORMAL_SEC = 120    # Every 2 minutes when target < 17 mph
COMP_TARGET_INTERVAL_ELEVATED_SEC = 90   # Every 90s when 17-18 mph
COMP_TARGET_INTERVAL_HIGH_SEC = 60       # Every 60s when 18-19 mph
COMP_TARGET_INTERVAL_CRITICAL_SEC = 45   # Every 45s when > 19 mph

# ---- Efficiency Screen Intervals ----
COMP_EFFICIENCY_INTERVAL_SEC = 120   # Every 2 minutes

# ---- Speed Alert Thresholds ----
COMP_ALERT_SLOW_DOWN_MPH = 18       # Target speed above this triggers "SLOW DOWN"
COMP_ALERT_SPEED_UP_MPH = 14        # Target speed below this triggers "SPEED UP"
COMP_ALERT_GRACE_PERIOD_SEC = 60    # No speed alerts for first 60 seconds
COMP_ALERT_DISPLAY_SEC = 2          # How long each speed alert is shown

# ---- Button Timing ----
COMP_EXTRA_LONG_PRESS_MS = 5000     # 5 seconds for extra-long press to exit competition mode


class Vehicle:
    def __init__(self):

        # State of the vehicle
        self.state = "DRIVE" # DRIVE, TEST, RACE, COMP
        self.logging_armed = True # Defaults to ON, toggle via Menu
        self.log_file_number = 0

        # Measured signals from the motor controller
        self.motor_ticks = 0
        self.smart_cruise = False
        self.motor_mph = 0.0 # From the motor controller
        self.speed_mph = 0.0 # Speed is the DIS's independent calculation
        self.rpm = 0
        self.voltage = 0.0
        self.current = 0.0
        self.throttle_position = 0.0
        self.throttle = 0
        self.duty_cycle = 0.0
        self.eco = False

        # Efficiency
        self.efficiency_instant = 0.0
        self.efficiency_total = 0.0
        self.EMA_ALPHA = 0.05 # Smoothing factor

        # Derived signals calculated onboard instantly (no time)
        self.distance_miles = 0.0
        self.power_instant = 0.0

        # Race / Timer State
        self.timer_running = False
        self.timer_state = "reset" # Reset, running, paused
        self.timer_elapsed_seconds = 0.0
        self.target_mph = 0.0
        self.remaining_distance_miles = 0.0
        self.remaining_time_seconds = 0.0

        # Derived signals calculated with time
        self.energy_consumed = 0.0

        # Constants
        self.TICKS_PER_MILE = 181515
        self.WHEEL_DIAMETER_IN = 16
        self.GOAL_DISTANCE_MI = GOAL_DISTANCE_MI
        self.GOAL_TIME_SEC = GOAL_TIME_SEC

        # Competition state
        self.comp_lap_count = 0       # 0 = not started, 1-3 = laps calibrated, 4 = finished
        self.comp_race_active = False # True while competition race is underway

        # Helpers
        self._last_update_ticks = time.ticks_ms()
        self._timer_start_ticks = 0
        self._stored_elapsed_ticks = 0 # Saves the time when paused
        self._prev_motor_ticks = 0
        self._ticks_at_race_start = 0  # For absolute ticks in comp mode

    def update_states(self, dt, current_time_ms):

        # Calculate Tick Delta
        delta_ticks = self.motor_ticks - self._prev_motor_ticks
        self._prev_motor_ticks = self.motor_ticks
        if delta_ticks < 0: delta_ticks = 0 # Handle wrap/reset

        # Update Speed
        if dt > 0:
            self.speed_mph = (delta_ticks / self.TICKS_PER_MILE) / (dt / 3600)
        else:
            self.speed_mph = 0.0

        # Update power instant
        self.power_instant = self.voltage * self.current

        # Update efficiency instant (Miles/kWh)
        power_kw = self.power_instant / 1000.0
        eff_inst_raw = 0.0
        if power_kw > 0.001:
            eff_inst_raw = self.speed_mph / power_kw
        elif self.speed_mph > 0.1:
            eff_inst_raw = 999.0 # Coasting

        if eff_inst_raw > 999.0: eff_inst_raw = 999.0
        self.efficiency_instant = (self.EMA_ALPHA * eff_inst_raw) + ((1 - self.EMA_ALPHA) * self.efficiency_instant)

        # Update Timer & Distance
        if self.timer_running:
            self.timer_elapsed_seconds = (self._stored_elapsed_ticks + time.ticks_diff(current_time_ms, self._timer_start_ticks)) / 1000

            # In competition mode, use absolute ticks for distance (resilient to DIS restart)
            if self.state == "COMP" and self.comp_race_active:
                self.distance_miles = self.motor_ticks / self.TICKS_PER_MILE
            else:
                self.distance_miles += delta_ticks / self.TICKS_PER_MILE

            # Update Energy (Wh) & Total Efficiency
            if dt > 0:
                self.energy_consumed += self.power_instant * (dt / 3600.0)

            energy_kwh = self.energy_consumed / 1000.0
            eff_total_raw = (self.distance_miles / energy_kwh) if energy_kwh > 0.0001 else 0.0
            if eff_total_raw > 999.0: eff_total_raw = 999.0
            self.efficiency_total = (self.EMA_ALPHA * eff_total_raw) + ((1 - self.EMA_ALPHA) * self.efficiency_total)
        else:
            self.timer_elapsed_seconds = self._stored_elapsed_ticks / 1000

        # Update Target MPH
        self.remaining_distance_miles = max(self.GOAL_DISTANCE_MI - self.distance_miles, 0)
        self.remaining_time_seconds = max(self.GOAL_TIME_SEC - self.timer_elapsed_seconds, 0.001)
        self.target_mph = (self.remaining_distance_miles / (self.remaining_time_seconds / 3600)) if self.remaining_time_seconds > 0 else 0
