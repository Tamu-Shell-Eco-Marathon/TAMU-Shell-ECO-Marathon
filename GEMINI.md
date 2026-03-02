# Project Context & Coding Guidelines: Eco-Marathon Display

## 0. Project Scope & Exclusions (STRICT)
* **Active Scope:** This context applies **ONLY** to the Python/MicroPython code running on the Raspberry Pi Pico (Display, Vehicle Logic, UART Manager).
* **Out of Bounds:**
    * **Motor Control Code (C Files):** Do NOT read, analyze, or suggest changes to any C files in this repository.
    * **Status:** The motor control code is under active, separate development. Treat it as unstable.
    * **Interaction:** Treat the Motor Controller strictly as a "Black Box" hardware device. We interact with it **only** via the UART byte protocol defined in `uart_manager.py`.

## 1. User Persona & Coding Style (CRITICAL)
* **Simplicity is King:** The maintainer is not an expert coder. Code must be readable, explicit, and easy to debug manually.
* **Avoid Abstractions:** Do not use complex Python features like:
    * Lambdas or List Comprehensions (unless extremely simple).
    * Complex Decorators (except `@property` for simple math).
    * Inheritance hierarchies (keep classes flat).
* **Variable Naming:** Use verbose, descriptive names.
    * *Bad:* `v`, `t`, `calc()`
    * *Good:* `vehicle_voltage`, `elapsed_time_ms`, `calculate_distance()`
* **Logic Flow:** Prefer explicit `if/elif/else` blocks over "clever" logic. It should be obvious what state the system is in just by reading the code.

## 2. Hardware Environment
* **Platform:** Raspberry Pi Pico (RP2040).
* **Language:** MicroPython.
* **Display:** Waveshare 1.3" OLED (SH1106 Driver). 128x64 resolution.
* **Inputs:** 2 Physical Buttons (Button A / Button B).
* **Comms:** UART connection to Motor Controller (4Hz update rate with plans to increase this in the future).
* **Constraints:**
    * **No Blocking:** Never use `time.sleep()` inside the main loop (except for tiny 1ms yields).
    * **Memory:** Limited RAM. Avoid creating large new objects in the loop.

## 3. Core Architecture
The system uses a "Star Topology" where the **Vehicle Class** is the center of the universe.

### A. The Vehicle Class (`vehicle_state.py`)
* **Role:** The "Source of Truth." Holds all signals (Speed, Volts, Amps), derived math (Distance, Energy), and Timer states.
* **Pattern:**
    * Hardware managers (UART) write *to* this class.
    * Display managers read *from* this class.
    * Physics calculations (Distance = Speed * Time) happen inside `vehicle.update_states()`.
* **Calibration:** Constants (Wheel Diameter, Ticks per Mile) live within this class for simplicity.

### B. The Display Manager (`display.py`)
* **Role:** Draws pixels based on `Vehicle` state. Does NOT perform business logic or math.
* **Modes:**
    1.  **Cluster Mode:** Carousel of screens (Speedo, Odo, Volts). Button A cycles, Button B enters Menu (via "Gatekeeper Screen").
    2.  **Menu Mode:** List-based settings. Button A scrolls, Button B selects/toggles.
    3.  **Race Mode:** Automated screen switching managed by `RaceManager`.

### C. The UART Manager (`uart_manager.py`)
* **Role:** Reads raw bytes from hardware, parses them, and updates `Vehicle` properties.
* **Sync:** Uses a "New Data" flag so `main.py` knows when to recalculate math.

### D. The Race Manager (PLANNED)
* **Role:** The "Digital Co-Pilot."
* **Function:** Monitors `Vehicle` data. Overrides the Display to show critical info (Timer, Alerts) based on logic (e.g., "Every 0.25 miles, show Odometer").
* **Input:** In Race Mode, ANY button press triggers the start timer.

## 4. Key Coding Patterns

### Handling Time
* **Do not use** `time.time()`.
* **Use** `time.ticks_ms()` and `time.ticks_diff(new, old)` for all intervals to avoid overflow errors.
* **Delta Time (dt):** Physics calculations must use `dt` to be frame-rate independent.

### The Main Loop (`main.py`)
* Must follow this specific flow:
    1.  `uart_manager.update()` (Get Inputs)
    2.  `vehicle.update_states()` (Update Physics)
    3.  `race_manager.update()` (Update Game Logic - Planned)
    4.  `button_manager.check_events()` (Process Buttons)
    5.  `display.draw_screen()` (Render Output)
    6.  `wdt.feed()` (Watchdog Timer - Safety)

## 5. Roadmap
1.  **Refactor Main:** Move logic into `Vehicle` class (In Progress).
2.  **Implement Menu:** Add "Gatekeeper" screen and Menu Mode logic.
3.  **Implement RaceManager:** Add the "Co-Pilot" logic for automated screen switching.
4.  **Logging:** (Future) Write vehicle stats to SD card/Storage.