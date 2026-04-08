import gc
import hardware
import utime as time
from display import DisplayManager, OLEDDriver, ButtonManager
from performance import PerformanceMonitor
from uart_manager import UartManager
from vehicle_state import Vehicle
from logger import Logger
from LED import TargetSpeedIndicator
from race_manager import RaceManager

# --- Hardware Setup ---
oled_driver = OLEDDriver()
display = DisplayManager(oled_driver)
button_manager = ButtonManager()

# --- Debug Flags ---
DEBUG_TSI = False
DEBUG_PERFORMANCE = False
DEBUG_VERBOSE = False
perf_monitor = (
    PerformanceMonitor(verbose=DEBUG_VERBOSE) if DEBUG_PERFORMANCE else None
)

# ---------------------- Main Program -----------------------

# --- Managers ---
uart_manager = UartManager(hardware.uart)
vehicle = Vehicle()
logger = Logger(interval_ms=1000)
tsi = TargetSpeedIndicator(data_pin=16, num_leds=14)
race_manager = RaceManager()

# ----------------- TIME VARIABLES -----------------
last_sample_time = time.ticks_ms()
elapsed_time = 0.0
sample_dt = 0.0
last_target_send_time = 0
last_energy_sync_time = 0
ENERGY_SYNC_INTERVAL_MS = 30000  # Sync energy to MC every 30 seconds
# ---------------------------------------------------

# =============== STARTUP RECOVERY ==================
# Wait for first S message from MC to detect competition mode recovery
print("DIS Initialized - waiting for motor controller state\n")

_query_start = time.ticks_ms()
_recovery_done = False
while time.ticks_diff(time.ticks_ms(), _query_start) < 500:
    uart_manager.update(vehicle)
    if uart_manager.new_data:
        if vehicle.state == "COMP":
            # Active competition race detected - recover state from S message
            race_manager.recover_from_s_message(vehicle, uart_manager, display)
            logger.start()
            print("RECOVERED: comp mode, elapsed={:.1f}s, ticks={}".format(
                uart_manager.last_elapsed_sec, vehicle.motor_ticks))
        _recovery_done = True
        break
    time.sleep_ms(10)

if not _recovery_done:
    print("No motor controller data - starting fresh")

# =============== MAIN LOOP =========================

while True:
    try:
        if perf_monitor: perf_monitor.loop_start()

        # Time Calculation always runs
        current_time = time.ticks_ms()
        sample_dt = time.ticks_diff(current_time, last_sample_time) / 1000
        last_sample_time = current_time

        # -------- Input Handling ---------------
        uart_manager.update(vehicle)

        # -------- Target Speed Sending (RACE and COMP modes) ---
        if vehicle.state in ("RACE", "COMP"):
            if time.ticks_diff(current_time, last_target_send_time) >= 1000:
                uart_manager.send("T,{:.1f}".format(vehicle.target_mph))
                last_target_send_time = current_time

        # --------- Derived Values (runs even with stale data)
        vehicle.update_states(sample_dt, current_time)

        # --------- TSI / Showroom LED ---------
        if display.showroom_active:
            tsi.showroom_update()
        else:
            tsi.update(vehicle)

        # --------- Button Handling -------------
        button_manager.update(vehicle, display, uart_manager, race_manager)

        # --------- Race Manager Activation & Update ---
        if vehicle.state == "COMP" and not race_manager.active:
            # Just entered comp mode (via menu) - activate race manager
            race_manager.start(display)
        elif vehicle.state != "COMP" and race_manager.active:
            # Left comp mode - deactivate race manager
            race_manager.stop()

        if vehicle.state == "COMP" and race_manager.active:
            race_manager.update(vehicle, display, uart_manager)

        # --------- Energy Sync to MC (periodic) ---
        if vehicle.state == "COMP" and vehicle.timer_running:
            if time.ticks_diff(current_time, last_energy_sync_time) >= ENERGY_SYNC_INTERVAL_MS:
                uart_manager.send_admin_energy(vehicle.energy_consumed)
                last_energy_sync_time = current_time

        # --------- LOGGING --------------------------------
        logger.update(vehicle, display)

        # --------- DISPLAY (always runs) ------------------
        if perf_monitor: perf_monitor.start()

        display.update(vehicle, uart_manager)

        if perf_monitor: perf_monitor.stop()

        # --------- DEBUG LOGGING ----------------------
        if perf_monitor:
            perf_monitor.loop_stop()
            if vehicle.timer_running:
                perf_monitor.update(
                    remaining_time=vehicle.remaining_time_seconds, remaining_dist=vehicle.remaining_distance_miles
                )
            else:
                perf_monitor.update()

        gc.collect()

    except MemoryError:
        gc.collect()
        print("MemoryError: recovered via gc.collect()")
    except Exception as e:
        print("Main loop error:", e)
