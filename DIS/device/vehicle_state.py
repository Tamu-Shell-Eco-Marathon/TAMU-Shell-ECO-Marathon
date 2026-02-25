# This class contains all of the states of the vehicle for all of the "signals" that we care about.
# It includes measured signals (from the motor controller) as well as derived signals

import utime as time
import math

class Vehicle:
    def __init__(self):

        # State of the vehicle
        self.state = "DRIVE"
        self.logging_armed = False # Toggle via Menu

        # Measured signals from the motor controller
        self.motor_ticks = 0
        self.smart_cruise = False
        self.motor_mph = 0.0
        self.rpm = 0
        self.voltage = 0.0
        self.current = 0.0
        self.throttle_position = 0.0
        self.throttle = 0
        self.throttle_request = 0.0
        self.duty_cycle = 0.0
        self.eco = False

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
        
        # Update power instant
        self.power_instant = self.voltage * self.current

        # Update Speed
        wheel_circumference_in = math.pi * self.WHEEL_DIAMETER_IN
        #self.motor_mph = self.rpm * wheel_circumference_in * 60 / 63360.0

        # Calculate Tick Delta
        delta_ticks = self.motor_ticks - self._prev_motor_ticks
        self._prev_motor_ticks = self.motor_ticks
        if delta_ticks < 0: delta_ticks = 0 # Handle wrap/reset

        # Update Timer & Distance
        if self.timer_running:
            self.timer_elapsed_seconds = (self._stored_elapsed_ticks + time.ticks_diff(current_time_ms, self._timer_start_ticks)) / 1000
            self.distance_miles += delta_ticks / self.TICKS_PER_MILE
        else:
            self.timer_elapsed_seconds = self._stored_elapsed_ticks / 1000

        # Update Target MPH
        self.remaining_distance_miles = max(self.GOAL_DISTANCE_MI - self.distance_miles, 0)
        self.remaining_time_seconds = max(self.GOAL_TIME_SEC - self.timer_elapsed_seconds, 0.001)
        self.target_mph = (self.remaining_distance_miles / (self.remaining_time_seconds / 3600)) if self.remaining_time_seconds > 0 else 0
