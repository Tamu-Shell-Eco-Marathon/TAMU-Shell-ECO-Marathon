# Competition Features Specification

This document describes two interconnected features for the Shell Eco-marathon competition: the **Race Manager** and **State Resynchronization**. Both features span the DIS (MicroPython, Pico) and the motor controller (C, Pico), communicating over the existing UART link.

---

## Table of Contents

1. [Feature 1: Race Manager](#feature-1-race-manager)
   - [Competition Mode](#competition-mode)
   - [Screen Scheduler](#screen-scheduler)
   - [Button Mapping](#button-mapping)
   - [Lap Distance Calibration](#lap-distance-calibration)
   - [Speed Alerts](#speed-alerts)
   - [Race Lifecycle](#race-lifecycle)
2. [Feature 2: State Resynchronization](#feature-2-state-resynchronization)
   - [Problem Statement](#problem-statement)
   - [Motor Controller State Storage](#motor-controller-state-storage)
   - [Administrative (A) Message Protocol](#administrative-a-message-protocol)
   - [Motor Ticks Reset on Race Start](#motor-ticks-reset-on-race-start)
   - [DIS Auto-Recovery](#dis-auto-recovery)
3. [UART Protocol Changes](#uart-protocol-changes)
4. [Configurable Parameters](#configurable-parameters)
5. [Files to Modify](#files-to-modify)

---

## Feature 1: Race Manager

### Competition Mode

A new vehicle mode called **Competition** (designator `'c'`) is added alongside the existing Drive (`'d'`), Race (`'r'`), and Test (`'t'`) modes.

**Motor controller behavior:** Competition mode behaves nearly identically to the existing Race mode. The motor controller uses the same smart cruise PID logic and target speed handling. The only distinction is the mode character `'c'` transmitted in telemetry and recognized in mode selection, which keeps the state synchronized between both controllers.

**DIS behavior:** Competition mode layers the Race Manager on top of the existing race mode functionality. This includes automatic screen scheduling, remapped buttons, lap calibration, speed alerts, and the remaining-time timer display. The Race Manager is a DIS-only concept; the motor controller does not handle any of these behaviors.

**Entry:** A new menu option `SET COMP MODE` is added to the existing DIS menu. When selected, the DIS sends `M,c` via UART. The motor controller acknowledges and enters competition mode. The DIS enters competition mode upon acknowledgment.

**Exit:** A 5-second extra-long press of either K0 or K1 exits competition mode. The DIS sends `M,d` to revert the motor controller to Drive mode. Menu access is completely disabled while in competition mode.

---

### Screen Scheduler

The screen scheduler automatically rotates the DIS display between screens during competition mode, removing the need for the driver to press buttons to view different gauges.

**Home Screen:** The speedometer (screen 0, MPH) is the default screen. Between any two non-speedometer screens, the speedometer must be displayed for **at least 30 seconds**. This ensures the driver is never "blind" to their current speed for extended periods.

**Screen Change Behavior:** When the scheduler switches to a non-speedometer screen, the display is **inverted for the first 1 second** to grab the driver's attention, then reverts to normal for the remaining display duration.

**Scheduled Screens:**

| Screen | Index | Display Duration | Trigger Interval | Notes |
|--------|-------|-----------------|------------------|-------|
| Remaining Time | 1 | 5 seconds | Every 5 minutes of elapsed time | Increases to every 1 minute when less than 5 minutes remain |
| Distance (Odometer) | 4 | 5 seconds | Every 1 mile of distance traveled | Triggers when `distance_miles` crosses a whole mile boundary |
| Target Speed | 5 | 5 seconds | Every 2 minutes | See importance escalation below |
| Cumulative Efficiency | 8 | 5 seconds | Every 2 minutes | Regular interval, no varying importance |

**Timer Display Change:** In competition mode, the timer screen (index 1) shows **remaining time** (`GOAL_TIME_SEC - timer_elapsed_seconds`) instead of elapsed time. The label should change from `ELAPSED` to `REMAINING` (or `REM`). The MM:SS format is preserved.

**Target Speed Importance Escalation:** As target speed increases, the vehicle is falling behind pace. The display interval for the target speed screen should decrease:

| Target Speed | Display Interval |
|-------------|-----------------|
| Below 17 mph | Every 2 minutes (normal) |
| 17 - 18 mph | Every 90 seconds |
| 18 - 19 mph | Every 60 seconds |
| Above 19 mph | Every 45 seconds |

**Scheduler Conflict Resolution:** If two screens are due to display at the same time, they are queued and shown sequentially. Each non-speedometer screen still requires the 30-second speedometer gap before the next non-speedometer screen can appear. The scheduler should maintain a simple FIFO queue of pending screen requests and process them one at a time.

**Scheduler Pseudocode:**

```
every main loop iteration:
    if competition_mode and timer_running:
        check each screen's trigger condition
        if triggered and not already queued:
            add to screen_request_queue

        if currently showing non-speedometer screen:
            if display_duration has elapsed:
                switch back to speedometer
                record speedometer_start_time

        if currently showing speedometer:
            if screen_request_queue is not empty:
                if time_on_speedometer >= 30 seconds:
                    pop next request from queue
                    switch to that screen
                    invert display for 1 second
                    start display_duration timer (5 seconds)
```

---

### Button Mapping

In competition mode, **K0 and K1 perform identical actions**, since the driver's gloved hand may not distinguish between them. Menu access is completely disabled.

**Three press tiers:**

| Press Type | Duration | Action | Feedback Alert |
|-----------|----------|--------|----------------|
| Short press | < 2 seconds | Lap recalibration (laps 1-3) | `LAP X` (where X is the lap number) |
| Long press | >= 2 seconds | Start race timer (first use only) | `RACE START` |
| Extra-long press | >= 5 seconds | Exit competition mode | `COMP EXIT` |

**Extra-long press detection** must not interfere with existing button handling. The implementation adds a third tier to the existing button state machine:

- At 2 seconds: fire `long_press` event (start timer). Show `RACE START` alert.
- Button still held at 5 seconds: fire `extra_long_press` event (exit competition mode). Show `COMP EXIT` alert.
- The long press at 2 seconds fires first. The extra-long press only fires if the button continues to be held. The `RACE START` alert shown at 2 seconds serves as feedback so the driver knows to release the button, preventing accidental triggering of the 5-second exit.

**Long press behavior after timer is started:** Once the timer is running, the long press (2s) has no additional action. Only short press (lap calibration) and extra-long press (exit) remain active. This prevents accidentally stopping or resetting the timer mid-race.

**Short press after all laps are calibrated:** After 3 lap calibrations have been recorded, additional short presses are ignored (no action, no alert).

---

### Lap Distance Calibration

The race consists of **4 laps**. The starting line and finish line are not in exactly the same location. During practice sessions, the team will measure the exact distance of the first 3 laps (from the start line back to the start line each time).

**Configurable known distances** (set before competition, defined at the top of the relevant file):

```python
# Lap calibration distances (miles) - measured during practice
COMP_LAP_1_DISTANCE = 2.39   # Cumulative distance at end of lap 1
COMP_LAP_2_DISTANCE = 4.78   # Cumulative distance at end of lap 2
COMP_LAP_3_DISTANCE = 7.17   # Cumulative distance at end of lap 3
```

**Calibration trigger:** When the driver does a short press at a lap crossing, the system compares the current measured `distance_miles` against the expected cumulative distance for that lap.

**Sanity check (10% margin):** The calibration is accepted only if:

```
abs(distance_miles - expected_lap_distance) <= 0.10 * (expected_lap_distance / lap_number)
```

Where `expected_lap_distance / lap_number` gives the per-lap distance. This prevents calibration from an accidental press far from the actual lap crossing.

- **Within margin:** Snap `distance_miles` to the known cumulative lap distance. Show alert `LAP X` (e.g., `LAP 1`). Increment lap counter.
- **Outside margin:** Reject the calibration. Show alert `BAD LAP`. Do not change distance or lap counter.

**Optional TICKS_PER_MILE adjustment:** A boolean toggle controls whether calibration also adjusts `TICKS_PER_MILE`:

```python
COMP_ADJUST_TICKS_PER_MILE = False  # Set to True during practice if calibration is needed
```

When enabled, at each successful calibration:

```python
actual_ticks = motor_ticks  # absolute ticks since race start
new_ticks_per_mile = actual_ticks / known_cumulative_distance
TICKS_PER_MILE = new_ticks_per_mile
```

This adjustment is also communicated to the motor controller (see Feature 2 - State Resynchronization) so both units use a consistent conversion factor.

---

### Speed Alerts

The alert system uses the existing `show_alert()` and `queue_alert()` methods combined with a brief display inversion to grab the driver's attention.

**Alert triggers:**

| Condition | Alert Text | Base Interval | Escalation |
|-----------|-----------|---------------|------------|
| `target_mph > 18` | `SLOW DOWN` | Every 60 seconds | Every 30s if > 19 mph, every 15s if > 20 mph |
| `target_mph < 14` | `SPEED UP` | Every 60 seconds | Every 30s if < 13 mph, every 15s if < 12 mph |

**Alert display:** Each speed alert is shown for **2 seconds** with the display inverted for the full duration. Speed alerts do not count as a "screen change" for the scheduler (they use the overlay alert system, not the screen switching system), so they do not reset the 30-second speedometer gap timer.

**Alert suppression:** Speed alerts should not fire during the first 60 seconds of the race (grace period for the vehicle to reach cruising speed). Alerts should also not fire while a non-speedometer screen is actively being displayed by the scheduler.

---

### Race Lifecycle

The complete competition flow from the driver's perspective:

1. **Pre-race setup:** Driver (or team member) navigates the DIS menu and selects `SET COMP MODE`. The DIS enters competition mode. The speedometer is displayed. Buttons are remapped.

2. **Race start:** Driver crosses the starting line and does a **long press** (2 seconds) of either button. The race timer starts. Motor ticks are reset to 0 (see Feature 2). Logging begins (if armed). Alert: `RACE START`.

3. **Lap 1 crossing:** Driver does a **short press** when crossing the start line after lap 1. Distance is calibrated if within margin. Alert: `LAP 1` or `BAD LAP`.

4. **Lap 2 crossing:** Short press. Calibration. Alert: `LAP 2` or `BAD LAP`.

5. **Lap 3 crossing:** Short press. Calibration. Alert: `LAP 3` or `BAD LAP`.

6. **Race finish (end of lap 4):** Driver does a **short press** at the finish line. Since all 3 calibration laps are used, this press stops the race timer and ends the competition. Logging stops. Alert: `RACE END`.

7. **Post-race:** Competition mode remains active (screens revert to manual control or static speedometer). Driver or team member does a **5-second extra-long press** to exit competition mode, or uses the menu if desired after exiting.

**Note on race end:** The timer does not auto-stop based on distance. The driver manually signals the finish with a button press. After lap 3's calibration is complete, the next short press is interpreted as the race finish rather than a calibration attempt.

---

## Feature 2: State Resynchronization

### Problem Statement

The DIS occasionally experiences brief power losses, causing it to revert to its default state (Drive mode, no timer, no distance, no logging). If this happens during a competition, the DIS loses all race context: elapsed time, distance traveled, energy consumed, vehicle mode, and lap count. The motor controller is much less likely to lose power.

The goal is to allow the DIS to **fully recover its competition state** by querying the motor controller on startup.

---

### Motor Controller State Storage

The motor controller must independently track the following race state variables (new additions to `motor_state.h`):

| Variable | Type | Description |
|----------|------|-------------|
| `race_timer_running` | `bool` | Whether the race timer is currently active |
| `race_timer_start` | `absolute_time_t` | Pico absolute time when the race was started |
| `race_elapsed_seconds` | `float` | Continuously calculated elapsed time |
| `comp_mode` | `bool` | Whether competition mode is active (alongside existing `race_mode`) |
| `comp_lap_count` | `uint8_t` | Current lap count (0-4) |
| `comp_energy_wh` | `float` | Cumulative energy consumed in Wh (calculated from `voltage_mv * battery_current_ma`) |

**Energy tracking on the motor controller:** The motor controller already has access to `voltage_mv` and `battery_current_ma` on every ADC interrupt. It can accumulate energy:

```c
// In the main telemetry loop (every UART_SEND_INTERVAL_US):
if (race_timer_running) {
    float power_w = (voltage_mv / 1000.0f) * (battery_current_ma / 1000.0f);
    float dt_hours = UART_SEND_INTERVAL_US / 1e6f / 3600.0f;
    comp_energy_wh += power_w * dt_hours;
}
```

---

### Administrative (A) Message Protocol

The `A` message prefix is used for administrative/synchronization messages between the DIS and motor controller.

**DIS to Motor Controller:**

| Message | Description |
|---------|-------------|
| `A,query` | DIS startup inquiry - requests full race state |
| `A,start` | Start the race timer and reset motor ticks to 0 |
| `A,lap,<N>` | Report lap crossing (N = lap number 1-3), update MC lap count |
| `A,energy,<Wh>` | Periodic energy sync from DIS to MC (keeps both in agreement) |
| `A,finish` | Race finished - stop timer on MC |

**Motor Controller to DIS:**

| Message | Description |
|---------|-------------|
| `A,state,<mode>,<timer_running>,<elapsed_sec>,<ticks>,<energy_wh>,<lap_count>` | Full state response to query |

**Example exchange on DIS startup recovery:**

```
DIS boots up, sends:     A,query,
MC responds:             A,state,c,1,847.3,154200,12.45,2
                         ^ mode=competition, timer=running, 847.3s elapsed,
                           154200 ticks, 12.45 Wh consumed, 2 laps completed
```

**Example exchange on race start:**

```
DIS sends:               A,start,
MC responds:             A,start,ACK
                         (MC resets motor_ticks to 0, starts race timer)
```

**Example exchange on lap crossing:**

```
DIS sends:               A,lap,1,
MC responds:             A,lap,1,ACK
                         (MC updates comp_lap_count to 1)
```

---

### Motor Ticks Reset on Race Start

Currently, motor ticks start at 0 when the motor controller powers up and never reset. The DIS uses an offset-based approach to calculate distance (recording the tick value when the timer starts).

**New behavior:** When the DIS sends `A,start` to begin the competition race timer, the motor controller:

1. Resets `motor_ticks` to 0
2. Starts `race_timer_running`
3. Records `race_timer_start = get_absolute_time()`
4. Resets `comp_energy_wh` to 0

This means `motor_ticks` now represents the **absolute distance traveled since race start**. The DIS no longer needs to track an offset. On recovery, the DIS can read `motor_ticks` directly from the normal `s,` telemetry message and convert to miles:

```python
distance_miles = motor_ticks / TICKS_PER_MILE
```

**Important:** The `reset_motor_ticks()` function already exists in `motor_state.c`. The reset should only happen on `A,start`, not on every mode change.

---

### DIS Auto-Recovery

When the DIS boots up, the following sequence occurs:

1. **Normal initialization** runs (display, UART, vehicle state, logger).

2. **Immediately after init**, the DIS sends `A,query` via UART.

3. **Wait for response** (with a short timeout, e.g., 500ms). If no response, assume no active race and continue normally in Drive mode.

4. **If response indicates an active race** (`timer_running == 1` and `mode == 'c'`):
   - Set `vehicle.state = "COMP"` (or whatever the competition state string is)
   - Set `vehicle.timer_running = True`
   - Reconstruct `vehicle._timer_start_ticks` from the elapsed seconds:
     ```python
     vehicle._stored_elapsed_ticks = int(elapsed_sec * 1000)
     vehicle._timer_start_ticks = time.ticks_ms()
     vehicle.timer_running = True
     vehicle.timer_state = 'running'
     ```
   - Set `vehicle.distance_miles = ticks / TICKS_PER_MILE` (using absolute ticks from telemetry)
   - Set `vehicle.energy_consumed = energy_wh`
   - Set lap count from response
   - **Arm and start logging** immediately
   - **Activate the Race Manager** (screen scheduler, alerts, etc.)
   - Show alert: `DIS RESET` (so the driver knows a power loss occurred)

5. **If response indicates no active race** (timer not running), continue with normal startup in whatever mode the MC reports.

**Ongoing resilience:** After recovery, the normal `s,` telemetry messages continue providing `motor_ticks` on every update. Since ticks are now absolute (reset at race start), the DIS can simply use `distance_miles = motor_ticks / TICKS_PER_MILE` rather than delta-based accumulation. This makes the distance calculation inherently resilient to DIS restarts. The DIS should still track delta_ticks for speed calculation, but distance should use the absolute value.

---

## UART Protocol Changes

### Telemetry Message (Motor Controller to DIS)

**Current format (10 fields):**
```
s,<ticks>,<UCO>,<mph>,<voltage_mv>,<current_ma>,<throttle_norm>,<throttle_mapped>,<duty_norm>,<mode>
```

**Updated format (10 fields, mode character expanded):**
The `mode` field now includes `'c'` for competition mode. No additional fields are needed in the telemetry message since race state is communicated via the `A` protocol.

```
Mode characters: 'd' = Drive, 'r' = Race, 'c' = Competition, 't' = Test, 'u' = Unknown
```

### Mode Command (DIS to Motor Controller)

**New mode character:**
```
M,c     -> Enter Competition mode (MC behaves like Race mode internally)
```

### Administrative Messages

See the [Administrative (A) Message Protocol](#administrative-a-message-protocol) section above for the full specification.

### Acknowledgment Behavior

The existing `send_acknowledgement()` function in `UART.c` echoes received messages with `,ACK` appended. This behavior is preserved for all new message types.

---

## Configurable Parameters

All configurable competition parameters should be defined as constants at the top of the relevant files, making them easy to adjust before a competition attempt.

### DIS Configuration (vehicle_state.py or new race_manager.py)

```python
# ---- Competition Race Parameters ----
GOAL_DISTANCE_MI = 9.56              # Total race distance (miles)
GOAL_TIME_SEC = 35 * 60              # Total race time (seconds)
COMP_NUM_LAPS = 4                    # Number of laps in the race

# ---- Lap Calibration Distances (miles, cumulative) ----
# Measured during practice session - UPDATE BEFORE COMPETITION
COMP_LAP_1_DISTANCE = 2.39           # Cumulative distance at end of lap 1
COMP_LAP_2_DISTANCE = 4.78           # Cumulative distance at end of lap 2
COMP_LAP_3_DISTANCE = 7.17           # Cumulative distance at end of lap 3

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
```

### Motor Controller Configuration (UART.h or motor_user_config.h)

```c
// Competition mode flag (alongside existing race_mode, drive_mode, test_mode)
volatile bool comp_mode = false;

// Race timer state
bool race_timer_running = false;
absolute_time_t race_timer_start;
float race_elapsed_seconds = 0.0f;

// Competition tracking
uint8_t comp_lap_count = 0;
float comp_energy_wh = 0.0f;
```

---

## Files to Modify

### DIS (MicroPython)

| File | Changes |
|------|---------|
| `vehicle_state.py` | Add competition state (`"COMP"`), competition config constants, remaining-time timer display support, absolute-ticks distance mode |
| `display.py` | Add extra-long press detection to `ButtonManager`, add competition button handling, add screen inversion control during scheduler transitions, add remaining time rendering |
| `main.py` | Integrate race manager update into main loop, add `A,query` on startup, handle competition-mode target speed sending |
| `uart_manager.py` | Parse `'c'` mode character, parse `A,state` responses, add `A,start`/`A,lap`/`A,finish` send methods |
| `menu.py` | Add `SET COMP MODE` menu option |
| `logger.py` | Support auto-start logging on DIS recovery (when race is discovered active) |
| **New: `race_manager.py`** | Screen scheduler, lap calibration logic, speed alert logic, competition mode state machine |

### Motor Controller (C)

| File | Changes |
|------|---------|
| `UART.c` | Add `'c'` to mode selection, parse `A` messages (query/start/lap/finish), send `A,state` responses, send `'c'` in telemetry |
| `UART.h` | Declare new A-message functions and variables |
| `motor_state.h` | Declare competition state variables (`comp_mode`, `race_timer_running`, `comp_lap_count`, `comp_energy_wh`) |
| `motor_state.c` | Implement race timer tracking (elapsed seconds calculation), energy accumulation, motor ticks reset on race start |
| `motor_control.c` | Add competition mode to control logic (same behavior as race mode) |
| `motor_user_config.c/h` | Add competition-specific defaults if needed |

---

## Implementation Notes

- **Race Manager as a separate module:** The race manager logic (screen scheduling, lap calibration, speed alerts) should be implemented as a new `race_manager.py` file on the DIS rather than embedded into `display.py` or `main.py`. This keeps the existing code clean and makes the competition logic easy to find and modify.

- **Absolute vs delta ticks:** After implementing the motor ticks reset on race start, the DIS should use absolute ticks for distance (`motor_ticks / TICKS_PER_MILE`) instead of accumulating deltas. Delta ticks are still needed for speed calculation. This is a key architectural change that makes the system resilient to DIS restarts.

- **Energy sync direction:** The DIS calculates energy from higher-resolution data (voltage * current every main loop iteration). The motor controller calculates energy independently at its telemetry rate. On DIS recovery, the MC's energy value is used as a starting point, and the DIS resumes accumulating from there. Periodic `A,energy` messages from the DIS keep the MC's value aligned with the DIS's more accurate calculation.

- **Testing the A-message protocol:** Before competition, the A-message recovery should be tested by simulating a DIS power loss (unplugging and replugging the DIS while the motor controller is running with an active timer). The DIS should recover all state within 1 second of booting.

- **MicroPython memory:** The race manager adds a new module and additional state. Monitor memory usage via `gc.mem_free()` to ensure it fits within the Pico's constraints. The screen scheduler queue should have a bounded size (max 4 entries).
