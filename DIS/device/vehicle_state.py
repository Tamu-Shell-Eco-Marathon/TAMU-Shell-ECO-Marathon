# This class contains all of the states of the vehicle for all of the "signals" that we care about.
# It includes measured signals (from the motor controller) as well as derived signals

import utime as time
import math

class Vehicle:
    def __init__(self):

        # State of the vehicle
        self.state = "DRIVE" # DRIVE, TEST, RACE
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
        self.GOAL_DISTANCE_MI = 1.0
        self.GOAL_TIME_SEC = 4 * 60

        # Helpers
        self._last_update_ticks = time.ticks_ms()
        self._timer_start_ticks = 0
        self._stored_elapsed_ticks = 0 # Saves the time when paused
        self._prev_motor_ticks = 0

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
