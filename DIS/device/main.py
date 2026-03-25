import gc
import hardware
import utime as time
from display import DisplayManager, OLEDDriver, ButtonManager
from performance import PerformanceMonitor
from uart_manager import UartManager
from vehicle_state import Vehicle
from logger import Logger
from LED import TargetSpeedIndicator

# --- Hardware Setup ---
oled_driver = OLEDDriver()
display = DisplayManager(oled_driver)
button_manager = ButtonManager()

# --- Debug Flags ---
#BEGIN DEMOOOOOOOOOOOOOOOO ALFREDO EDIT
DEBUG_TSI = False
#END DEMOOOOOOOOOOOOOOOO ALFREDO EDIT
DEBUG_PERFORMANCE = False
DEBUG_VERBOSE = False
DEBUG_TIMER_SYNC = False
perf_monitor = (
    PerformanceMonitor(verbose=DEBUG_VERBOSE) if DEBUG_PERFORMANCE else None
)

# ---------------------- Main Program -----------------------

# --- Managers ---
uart_manager = UartManager(hardware.uart)
vehicle = Vehicle()
logger = Logger(interval_ms=1000)
tsi = TargetSpeedIndicator(data_pin=16, num_leds=14)

# ----------------- TIME VARIABLES -----------------
last_sample_time = time.ticks_ms()
elapsed_time = 0.0
sample_dt = 0.0
last_target_send_time = 0
last_sync_print_time = 0
# ---------------------------------------------------

print("DIS Initialized\n")

while True:
    try:
        if perf_monitor: perf_monitor.loop_start()

        # Time Calculation always runs
        current_time = time.ticks_ms()
        sample_dt = time.ticks_diff(current_time, last_sample_time) / 1000
        last_sample_time = current_time

        # -------- Input Handling ---------------
        uart_manager.update(vehicle)

        # -------- Race Start ACK ---------------
        if vehicle.race_started_ack:
            vehicle.race_started_ack = False
            display.show_alert("RACE", "START", 2)

        # -------- Race Timer Sync ---------------
        if vehicle.timer_running and vehicle.mc_race_seconds > 0:
            mismatch = vehicle.timer_elapsed_seconds - vehicle.mc_race_seconds
            if abs(mismatch) > 5.0:
                if vehicle.mc_race_seconds > vehicle.timer_elapsed_seconds:
                    # MC has longer timer — DIS adopts MC's time
                    vehicle._stored_elapsed_ticks = int(vehicle.mc_race_seconds * 1000)
                    vehicle._timer_start_ticks = current_time
                elif vehicle.timer_elapsed_seconds > vehicle.mc_race_seconds:
                    # DIS has longer timer — tell MC to sync
                    uart_manager.send("A,sync,{:.1f}".format(vehicle.timer_elapsed_seconds))

            if DEBUG_TIMER_SYNC:
                if time.ticks_diff(current_time, last_sync_print_time) >= 1000:
                    print("SYNC: DIS={:.1f}s MC={:.1f}s mismatch={:.1f}s".format(
                        vehicle.timer_elapsed_seconds, vehicle.mc_race_seconds, mismatch))
                    last_sync_print_time = current_time

        if vehicle.state == "RACE":
            if time.ticks_diff(current_time, last_target_send_time) >= 1000:
                uart_manager.send("T,{:.1f}".format(vehicle.target_mph))
                last_target_send_time = current_time


        # --------- Derived Values (runs even with stale data)
        vehicle.update_states(sample_dt, current_time)

        tsi.update(vehicle)

        button_manager.update(vehicle, display, uart_manager)

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
