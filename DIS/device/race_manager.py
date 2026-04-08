import utime as time
from vehicle_state import (
    COMP_LAP_DISTANCES, COMP_CALIBRATION_MARGIN, COMP_ADJUST_TICKS_PER_MILE,
    COMP_SPEEDOMETER_MIN_SEC, COMP_SCREEN_DISPLAY_SEC, COMP_SCREEN_INVERT_SEC,
    COMP_TIMER_INTERVAL_SEC, COMP_TIMER_URGENT_THRESHOLD, COMP_TIMER_URGENT_INTERVAL_SEC,
    COMP_ODOMETER_INTERVAL_MI,
    COMP_TARGET_INTERVAL_NORMAL_SEC, COMP_TARGET_INTERVAL_ELEVATED_SEC,
    COMP_TARGET_INTERVAL_HIGH_SEC, COMP_TARGET_INTERVAL_CRITICAL_SEC,
    COMP_EFFICIENCY_INTERVAL_SEC,
    COMP_ALERT_SLOW_DOWN_MPH, COMP_ALERT_SPEED_UP_MPH,
    COMP_ALERT_GRACE_PERIOD_SEC, COMP_ALERT_DISPLAY_SEC,
    GOAL_TIME_SEC,
)

# Screen indices matching display.py carousel
SCREEN_MPH = 0
SCREEN_TIMER = 1
SCREEN_ODOMETER = 4
SCREEN_TARGET = 5
SCREEN_EFFICIENCY = 8

_SCREEN_NAMES = {
    SCREEN_MPH: "Speedometer",
    SCREEN_TIMER: "Timer",
    SCREEN_ODOMETER: "Odometer",
    SCREEN_TARGET: "Target Speed",
    SCREEN_EFFICIENCY: "Efficiency",
}


class RaceManager:
    """
    Manages competition mode behavior:
    - Screen scheduler (auto-rotate screens with priority)
    - Lap distance calibration
    - Speed alerts
    - Button handling (unified K0/K1)
    """

    def __init__(self):
        self.active = False

        # --- Screen Scheduler State ---
        self._current_showing = SCREEN_MPH  # Which screen is actively displayed
        self._speedometer_start = 0         # When we last switched TO speedometer
        self._screen_display_start = 0      # When the current non-MPH screen started showing
        self._screen_queue = []             # FIFO queue of pending screen requests (max 4)
        self._showing_non_mph = False       # True while a scheduled screen is active

        # --- Trigger Tracking (to avoid duplicate triggers) ---
        self._last_timer_trigger_sec = 0    # Last elapsed second at which timer screen was triggered
        self._last_odometer_trigger_mi = 0  # Last mile boundary that triggered odometer
        self._last_target_trigger = 0       # ticks_ms when target screen was last triggered
        self._last_efficiency_trigger = 0   # ticks_ms when efficiency screen was last triggered

        # --- Speed Alert State ---
        self._last_speed_alert = 0          # ticks_ms of last speed alert

        # --- Lap Calibration State ---
        # (comp_lap_count and comp_race_active live on vehicle)

    def _fmt_time(self, seconds):
        m = int(seconds) // 60
        s = int(seconds) % 60
        return "{}:{:02d}".format(m, s) if m > 0 else ":{}".format(s)

    def _screen_name(self, index):
        return _SCREEN_NAMES.get(index, "Screen[{}]".format(index))

    def _queue_names(self):
        return [self._screen_name(s) for s in self._screen_queue]

    def start(self, display):
        """Activate the race manager (called when entering comp mode or recovering)."""
        self.active = True
        now = time.ticks_ms()
        self._current_showing = SCREEN_MPH
        self._speedometer_start = now
        self._screen_display_start = 0
        self._screen_queue = []
        self._showing_non_mph = False
        self._last_timer_trigger_sec = 0
        self._last_odometer_trigger_mi = 0
        self._last_target_trigger = now
        self._last_efficiency_trigger = now
        self._last_speed_alert = now
        display.current_screen = SCREEN_MPH
        print("Race Manager: ACTIVATED")

    def stop(self):
        """Deactivate the race manager."""
        self.active = False
        print("Race Manager: DEACTIVATED")

    # =========================================================================
    # MAIN UPDATE (called every main loop iteration)
    # =========================================================================

    def update(self, vehicle, display, uart_manager):
        """Called every main loop iteration while in competition mode."""
        if not self.active or not vehicle.timer_running:
            return

        now = time.ticks_ms()
        elapsed = vehicle.timer_elapsed_seconds

        # --- Check screen triggers ---
        self._check_timer_trigger(vehicle, elapsed)
        self._check_odometer_trigger(vehicle)
        self._check_target_trigger(vehicle, now)
        self._check_efficiency_trigger(now)

        # --- Process screen scheduler ---
        self._process_scheduler(display, now, vehicle)

        # --- Speed alerts ---
        self._check_speed_alerts(vehicle, display, elapsed, now)

    # =========================================================================
    # BUTTON HANDLING (called from ButtonManager when in COMP mode)
    # =========================================================================

    def handle_button(self, click, hold, extra_long, vehicle, display, uart_manager):
        """
        Handle unified button input in competition mode.
        click = short press, hold = long press (2s), extra_long = 5s press
        """
        now = time.ticks_ms()

        # --- Extra-long press: Exit competition mode ---
        if extra_long:
            self._exit_competition(vehicle, display, uart_manager)
            return

        # --- Long press: Start race timer (first time only) ---
        if hold:
            if not vehicle.timer_running and not vehicle.comp_race_active:
                self._start_race(vehicle, display, uart_manager, now)
            return

        # --- Short press: Lap calibration or race finish ---
        if click:
            if not vehicle.comp_race_active:
                return  # Ignore clicks before race starts

            if vehicle.comp_lap_count < 3:
                # Laps 1-3: attempt calibration
                self._attempt_calibration(vehicle, display, uart_manager)
            elif vehicle.comp_lap_count == 3:
                # After 3 calibrations, next click = race finish
                self._finish_race(vehicle, display, uart_manager, now)
            # comp_lap_count >= 4: ignore (race already finished)

    # =========================================================================
    # RACE LIFECYCLE
    # =========================================================================

    def _start_race(self, vehicle, display, uart_manager, now):
        """Start the competition race timer."""
        vehicle._timer_start_ticks = now
        vehicle._stored_elapsed_ticks = 0
        vehicle.timer_running = True
        vehicle.timer_state = 'running'
        vehicle.comp_race_active = True
        vehicle.comp_lap_count = 0
        vehicle.distance_miles = 0.0
        vehicle.energy_consumed = 0.0
        vehicle.efficiency_total = 0.0

        # Tell MC to reset ticks and start its timer
        uart_manager.send_admin_start()

        # Reset scheduler triggers
        self._speedometer_start = now
        self._last_timer_trigger_sec = 0
        self._last_odometer_trigger_mi = 0
        self._last_target_trigger = now
        self._last_efficiency_trigger = now
        self._last_speed_alert = now

        display.show_alert("RACE", "START", 2)
        print("Race Manager: RACE START")

    def _finish_race(self, vehicle, display, uart_manager, now):
        """Finish the competition race."""
        vehicle.comp_lap_count = 4
        vehicle.timer_running = False
        vehicle.timer_state = 'reset'
        vehicle.comp_race_active = False
        vehicle._stored_elapsed_ticks = int(vehicle.timer_elapsed_seconds * 1000)

        uart_manager.send_admin_finish()
        display.show_alert("RACE", "END", 3)
        print("Race Manager: RACE END | elapsed={}".format(self._fmt_time(vehicle.timer_elapsed_seconds)))

    def _exit_competition(self, vehicle, display, uart_manager):
        """Exit competition mode entirely."""
        if vehicle.comp_race_active:
            vehicle.timer_running = False
            vehicle.timer_state = 'reset'
            vehicle.comp_race_active = False
            vehicle._stored_elapsed_ticks = int(vehicle.timer_elapsed_seconds * 1000)
            uart_manager.send_admin_finish()

        self.stop()
        # Switch to drive mode
        uart_manager.send("M,d")
        vehicle.state = "DRIVE"
        display.current_screen = SCREEN_MPH
        display.show_alert("COMP", "EXIT", 2)
        print("Race Manager: COMP EXIT")

    # =========================================================================
    # LAP CALIBRATION
    # =========================================================================

    def _attempt_calibration(self, vehicle, display, uart_manager):
        """Attempt to calibrate distance at a lap crossing."""
        lap_index = vehicle.comp_lap_count  # 0-based: which lap we're completing
        if lap_index >= len(COMP_LAP_DISTANCES):
            return

        expected_distance = COMP_LAP_DISTANCES[lap_index]
        per_lap_distance = expected_distance / (lap_index + 1)
        margin = COMP_CALIBRATION_MARGIN * per_lap_distance

        if abs(vehicle.distance_miles - expected_distance) <= margin:
            # Calibration accepted
            vehicle.distance_miles = expected_distance

            if COMP_ADJUST_TICKS_PER_MILE and vehicle.motor_ticks > 0:
                vehicle.TICKS_PER_MILE = int(vehicle.motor_ticks / expected_distance)

            vehicle.comp_lap_count = lap_index + 1
            uart_manager.send_admin_lap(vehicle.comp_lap_count)
            display.show_alert("LAP", str(vehicle.comp_lap_count), 2)
            display.set_invert(1)
            print("Race Manager: LAP {} accepted | dist={:.3f}mi (expected {:.3f}mi)".format(
                vehicle.comp_lap_count, expected_distance, expected_distance))
        else:
            # Calibration rejected
            display.show_alert("BAD", "LAP", 2)
            display.set_invert(1)
            print("Race Manager: LAP rejected | dist={:.3f}mi (expected {:.3f}mi, margin={:.3f}mi)".format(
                vehicle.distance_miles, expected_distance, margin))

    # =========================================================================
    # SCREEN SCHEDULER
    # =========================================================================

    def _enqueue_screen(self, screen_index):
        """Add a screen to the scheduler queue if not already queued."""
        if screen_index not in self._screen_queue and len(self._screen_queue) < 4:
            self._screen_queue.append(screen_index)
            print("Race Manager: Queued {} | queue={}".format(
                self._screen_name(screen_index), self._queue_names()))

    def _check_timer_trigger(self, vehicle, elapsed):
        """Check if the timer screen should be shown."""
        remaining = GOAL_TIME_SEC - elapsed
        if remaining <= COMP_TIMER_URGENT_THRESHOLD:
            interval = COMP_TIMER_URGENT_INTERVAL_SEC
        else:
            interval = COMP_TIMER_INTERVAL_SEC

        # Trigger at each interval boundary
        current_boundary = int(elapsed / interval) * interval
        if current_boundary > 0 and current_boundary > self._last_timer_trigger_sec:
            self._last_timer_trigger_sec = current_boundary
            self._enqueue_screen(SCREEN_TIMER)

    def _check_odometer_trigger(self, vehicle):
        """Check if the odometer screen should be shown."""
        current_mile = int(vehicle.distance_miles / COMP_ODOMETER_INTERVAL_MI)
        if current_mile > 0 and current_mile > self._last_odometer_trigger_mi:
            self._last_odometer_trigger_mi = current_mile
            self._enqueue_screen(SCREEN_ODOMETER)

    def _check_target_trigger(self, vehicle, now):
        """Check if the target speed screen should be shown."""
        target = vehicle.target_mph
        if target >= 19:
            interval_ms = COMP_TARGET_INTERVAL_CRITICAL_SEC * 1000
        elif target >= 18:
            interval_ms = COMP_TARGET_INTERVAL_HIGH_SEC * 1000
        elif target >= 17:
            interval_ms = COMP_TARGET_INTERVAL_ELEVATED_SEC * 1000
        else:
            interval_ms = COMP_TARGET_INTERVAL_NORMAL_SEC * 1000

        if time.ticks_diff(now, self._last_target_trigger) >= interval_ms:
            self._last_target_trigger = now
            self._enqueue_screen(SCREEN_TARGET)

    def _check_efficiency_trigger(self, now):
        """Check if the efficiency screen should be shown."""
        interval_ms = COMP_EFFICIENCY_INTERVAL_SEC * 1000
        if time.ticks_diff(now, self._last_efficiency_trigger) >= interval_ms:
            self._last_efficiency_trigger = now
            self._enqueue_screen(SCREEN_EFFICIENCY)

    def _process_scheduler(self, display, now, vehicle):
        """Process the screen scheduler: switch screens as needed."""
        if self._showing_non_mph:
            # Currently showing a scheduled screen - check if duration has elapsed
            display_ms = COMP_SCREEN_DISPLAY_SEC * 1000
            if time.ticks_diff(now, self._screen_display_start) >= display_ms:
                # Return to speedometer
                self._showing_non_mph = False
                self._current_showing = SCREEN_MPH
                self._speedometer_start = now
                display.current_screen = SCREEN_MPH
                next_name = self._queue_names()[0] if self._screen_queue else "none"
                print("Race Manager: Showing Speedometer ({}) | Next: {}".format(
                    self._fmt_time(vehicle.timer_elapsed_seconds), next_name))
        else:
            # Currently on speedometer - check if we can show queued screen
            if self._screen_queue:
                min_gap_ms = COMP_SPEEDOMETER_MIN_SEC * 1000
                if time.ticks_diff(now, self._speedometer_start) >= min_gap_ms:
                    # Show next queued screen
                    next_screen = self._screen_queue.pop(0)
                    self._showing_non_mph = True
                    self._current_showing = next_screen
                    self._screen_display_start = now
                    display.current_screen = next_screen
                    # Invert display briefly to grab attention
                    display.set_invert(COMP_SCREEN_INVERT_SEC)
                    next_name = self._queue_names()[0] if self._screen_queue else "Speedometer"
                    print("Race Manager: Showing {} ({}) | Next: {}".format(
                        self._screen_name(next_screen),
                        self._fmt_time(vehicle.timer_elapsed_seconds),
                        next_name))

    # =========================================================================
    # SPEED ALERTS
    # =========================================================================

    def _check_speed_alerts(self, vehicle, display, elapsed, now):
        """Check and fire speed alerts based on target speed."""
        # Grace period at start of race
        if elapsed < COMP_ALERT_GRACE_PERIOD_SEC:
            return

        # Don't alert while a non-speedometer screen is showing
        if self._showing_non_mph:
            return

        target = vehicle.target_mph
        alert_text = None
        interval_ms = 0

        if target > COMP_ALERT_SLOW_DOWN_MPH:
            alert_text = ("SPEED", "UP")
            overshoot = target - COMP_ALERT_SLOW_DOWN_MPH
            if overshoot > 2:
                interval_ms = 15000
            elif overshoot > 1:
                interval_ms = 30000
            else:
                interval_ms = 60000

        elif target < COMP_ALERT_SPEED_UP_MPH:
            alert_text = ("SLOW", "DOWN")
            undershoot = COMP_ALERT_SPEED_UP_MPH - target
            if undershoot > 2:
                interval_ms = 15000
            elif undershoot > 1:
                interval_ms = 30000
            else:
                interval_ms = 60000

        if alert_text and time.ticks_diff(now, self._last_speed_alert) >= interval_ms:
            self._last_speed_alert = now
            display.queue_alert(alert_text[0], alert_text[1], COMP_ALERT_DISPLAY_SEC)
            display.set_invert(COMP_ALERT_DISPLAY_SEC)
            print("Race Manager: ALERT {} {} | target={:.1f}mph elapsed={}".format(
                alert_text[0], alert_text[1], target,
                self._fmt_time(elapsed)))

    # =========================================================================
    # STATE RECOVERY (for DIS power loss)
    # =========================================================================

    def recover_from_admin(self, admin_data, vehicle, display, uart_manager):
        """
        Recover competition state from motor controller's A,state response.
        Called during DIS startup if an active race is detected.
        """
        vehicle.state = "COMP"
        vehicle.comp_race_active = True
        vehicle.comp_lap_count = admin_data['lap_count']

        # Reconstruct timer
        elapsed_ms = int(admin_data['elapsed_sec'] * 1000)
        vehicle._stored_elapsed_ticks = elapsed_ms
        vehicle._timer_start_ticks = time.ticks_ms()
        vehicle.timer_running = True
        vehicle.timer_state = 'running'

        # Distance from absolute ticks
        vehicle.motor_ticks = admin_data['ticks']
        vehicle._prev_motor_ticks = admin_data['ticks']
        vehicle.distance_miles = admin_data['ticks'] / vehicle.TICKS_PER_MILE

        # Energy
        vehicle.energy_consumed = admin_data['energy_wh']

        # Activate race manager
        self.start(display)

        # Reset trigger tracking based on recovered state
        elapsed = admin_data['elapsed_sec']
        self._last_timer_trigger_sec = int(elapsed / COMP_TIMER_INTERVAL_SEC) * COMP_TIMER_INTERVAL_SEC
        self._last_odometer_trigger_mi = int(vehicle.distance_miles / COMP_ODOMETER_INTERVAL_MI)

        display.show_alert("DIS", "RESET", 2)
        print("Race Manager: RECOVERED | elapsed={} laps={} dist={:.3f}mi energy={:.2f}Wh".format(
            self._fmt_time(admin_data['elapsed_sec']),
            admin_data['lap_count'],
            vehicle.distance_miles,
            vehicle.energy_consumed))

    def recover_from_s_message(self, vehicle, uart_manager, display):
        """
        Recover competition state from the first S message after DIS power loss.
        Elapsed time and distance are recovered from S message data.
        Lap count and energy reset to 0 (not available in S messages).
        """
        admin_data = {
            'mode': 'c',
            'timer_running': True,
            'elapsed_sec': uart_manager.last_elapsed_sec,
            'ticks': vehicle.motor_ticks,
            'energy_wh': 0.0,
            'lap_count': 0,
        }
        self.recover_from_admin(admin_data, vehicle, display, uart_manager)
