import os
import utime as time

class Logger:
    def __init__(self, interval_ms=1000):
        self.interval_ms = interval_ms
        self.last_log_time = 0
        self.file = None
        self.is_logging = False
        self.filename = ""
        
        # Define columns once to ensure header matches data
        self.columns = [
            "Time", "State", "Ticks", "Speed", "Target", "SmartCruise", 
            "Volts", "Amps", "PowerInst", "Throttle", "Duty", "RPM"
        ]
        
        self._ensure_directory()
        self._prev_timer_running = False

    def _ensure_directory(self):
        """Check if /Logs exists, create if not."""
        try:
            os.mkdir("/Logs")
        except OSError:
            pass # Directory likely exists

    def _get_next_filename(self):
        """Scan /Logs to find the next incremental filename."""
        max_num = 0
        try:
            files = os.listdir("/Logs")
            for f in files:
                if f.startswith("log_") and f.endswith(".csv"):
                    try:
                        # Parse "log_X.csv" -> X
                        num_part = f.split('_')[1].split('.')[0]
                        num = int(num_part)
                        if num > max_num:
                            max_num = num
                    except (ValueError, IndexError):
                        continue
        except OSError:
            pass # Directory might be empty or error reading it
            
        return "/Logs/log_{}.csv".format(max_num + 1)

    def start(self):
        """Open file and write header."""
        if self.is_logging: return

        self.filename = self._get_next_filename()
        print(f"Starting Log: {self.filename}")
        
        try:
            self.file = open(self.filename, "w")
            # Write Header
            header = ",".join(self.columns) + "\n"
            self.file.write(header)
            self.file.flush() # Ensure header is written
            self.is_logging = True
            self.last_log_time = time.ticks_ms()
        except Exception as e:
            print(f"Log Start Error: {e}")
            self.is_logging = False

    def stop(self, display=None):
        """Close file and notify user."""
        if not self.is_logging: return

        print(f"Stopping Log: {self.filename}")
        
        if display:
            display.show_alert("SAVING", "LOG", 2)

        try:
            if self.file:
                self.file.close()
                self.file = None
                if display:
                    display.show_alert("LOG", "SAVED", 2)
        except Exception as e:
            print(f"Log Stop Error: {e}")
        
        self.is_logging = False

    def update(self, vehicle, display):
        """Main loop update. Handles state transitions and interval writing."""
        
        # --- State Machine for Start/Stop ---
        # Rising Edge of Timer: Start if Armed
        if vehicle.timer_running and not self._prev_timer_running:
            if vehicle.logging_armed:
                self.start()
        
        # Falling Edge of Timer: Stop if Logging
        if not vehicle.timer_running and self._prev_timer_running:
            if self.is_logging:
                self.stop(display)

        self._prev_timer_running = vehicle.timer_running

        # --- Periodic Writing ---
        if self.is_logging:
            now = time.ticks_ms()
            if time.ticks_diff(now, self.last_log_time) >= self.interval_ms:
                self.write_row(vehicle)
                self.last_log_time = now

    def write_row(self, vehicle):
        """Formats and writes a single row of data."""
        try:
            # Format data to 2 decimal places for floats
            row_data = [
                "{:.2f}".format(vehicle.timer_elapsed_seconds), #Time
                str(vehicle.state),                             #State
                str(vehicle.motor_ticks),                       #Ticks
                "{:.2f}".format(vehicle.motor_mph),             #Speed
                "{:.2f}".format(vehicle.target_mph),            #Target
                "1" if vehicle.smart_cruise else "0",           #SmartCruise
                "{:.2f}".format(vehicle.voltage),               #Volts
                "{:.2f}".format(vehicle.current),               #Amps
                "{:.2f}".format(vehicle.power_instant),         #PowerInst
                str(vehicle.throttle),                          #Throttle
                str(vehicle.duty_cycle),                        #Duty
                str(vehicle.rpm)                                #RPM
            ]
            
            line = ",".join(row_data) + "\n"
            if self.file:
                self.file.write(line)
                self.file.flush() # Critical: Save to disk immediately
            
        except Exception as e:
            print(f"Log Write Error: {e}")
            # Optional: Stop logging if write fails to avoid cascading errors
            # self.stop() 
