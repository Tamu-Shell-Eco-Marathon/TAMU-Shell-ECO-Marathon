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
# ---------------------------------------------------

print("DIS Initialized\n")

while True:

    # Time Calculation always runs
    current_time = time.ticks_ms()
    sample_dt = time.ticks_diff(current_time, last_sample_time) / 1000
    last_sample_time = current_time

    # -------- Input Handling ---------------
    uart_manager.update(vehicle)

    if vehicle.state == "RACE":
        if time.ticks_diff(current_time, last_target_send_time) >= 1000:
            uart_manager.send("T,{:.1f}".format(vehicle.target_mph))
            last_target_send_time = current_time


    # --------- Derived Values (runs even with stale data)
    vehicle.update_states(sample_dt, current_time)
    # #BEGIN DEMOOOOOOOOOOOOOOOO ALFREDO EDIT
    # if DEBUG_TSI:
    #     vehicle.state = "RACE"          # force race mode ON so LEDs are allowed
    #     vehicle.smart_cruise = False
        
    #     vehicle.target_mph = 18.0
    #     vehicle.motor_mph = 12.0 + (time.ticks_ms() // 1500) % 10  # 12..21 repeating
    # #END DEMOOOOOOOOOOOOOOOO ALFREDO EDIT



    tsi.update(vehicle)


    # tsi.update(
    #     current_speed=vehicle.motor_mph,
    #     target_speed=vehicle.target_mph,
    #     race_mode=(vehicle.state == "RACE"),
    #     smart_cruise=vehicle.smart_cruise
    # )


    button_manager.update(vehicle, display, uart_manager)

    # --------- LOGGING --------------------------------
    logger.update(vehicle, display)

    # --------- DISPLAY (always runs) ------------------
    if perf_monitor: perf_monitor.start()

    display.update(vehicle, uart_manager)

    if perf_monitor: perf_monitor.stop()

    # --------- DEBUG LOGGING ----------------------
    if perf_monitor:
        if vehicle.timer_running:
            # Pass race data when the timer is active
            perf_monitor.update(
                remaining_time=vehicle.remaining_time_seconds, remaining_dist=vehicle.remaining_distance_miles
            )
        else:
            # Otherwise, just update for performance stats
            perf_monitor.update()
