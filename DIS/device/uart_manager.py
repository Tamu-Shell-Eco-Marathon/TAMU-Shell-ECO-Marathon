class UartManager:
    def __init__(self, uart_instance):
        self.uart = uart_instance
        self.buffer = bytearray()

        self.uart_blink = False
        self.new_data = False # Flag to indicate if new data was parsed
        self.last_message = None # Store last message for polling

        # Admin response storage (populated by A,state responses)
        self.admin_response = None

    def update(self, vehicle):
        """
        Reads from UART, parses messages, and updates internal state.
        Should be called once per main loop iteration.
        """
        self.new_data = False
        if self.uart.any():
            data = self.uart.read()
            if data:
                # Append printable characters and newlines into bytearray
                for b in data:
                    if 32 <= b <= 126 or b == 10:
                        self.buffer.append(b)

                # Process complete lines
                while b'\n' in self.buffer:
                    idx = self.buffer.index(b'\n')
                    line = str(self.buffer[:idx], 'utf-8').strip()
                    self.buffer = self.buffer[idx + 1:]
                    if not line:
                        continue

                    self._parse_line(line, vehicle)
                    self.new_data = True
                    self.uart_blink = not self.uart_blink

    def _parse_line(self, line, vehicle):
        """Parses a single line of data from the UART."""
        try:
            self.last_message = line # Store for read_message()

            if line.startswith("s,"):
                parts = line.split(',')
                if len(parts) >= 10:
                    vehicle.motor_ticks = int(parts[1])
                    vehicle.smart_cruise = bool(int(parts[2]))
                    vehicle.motor_mph = float(parts[3])
                    vehicle.rpm = int(vehicle.motor_mph / 0.04767)
                    vehicle.voltage = int(parts[4]) / 1000.0
                    vehicle.current = int(parts[5]) / 1000.0
                    vehicle.throttle_position = int(parts[6])
                    vehicle.throttle = int(parts[7])
                    if vehicle.throttle > 100:
                        vehicle.throttle = 100
                    vehicle.duty_cycle = int(parts[8])
                    mode_char = parts[9].strip()
                    if mode_char == 'c':
                        vehicle.state = "COMP"
                    elif mode_char == 'r':
                        vehicle.state = "RACE"
                    elif mode_char == 't':
                        vehicle.state = "TEST"
                    elif mode_char == 'd':
                        vehicle.state = "DRIVE"

            elif line.startswith("A,state,"):
                # Admin state response: A,state,<mode>,<timer>,<elapsed>,<ticks>,<energy>,<laps>
                self._parse_admin_state(line)

        except Exception as e:
            print("Parse error:", e, "on line:", line)

    def _parse_admin_state(self, line):
        """Parse A,state response from motor controller."""
        try:
            parts = line.split(',')
            if len(parts) >= 8:
                self.admin_response = {
                    'mode': parts[2].strip(),
                    'timer_running': int(parts[3]) == 1,
                    'elapsed_sec': float(parts[4]),
                    'ticks': int(parts[5]),
                    'energy_wh': float(parts[6]),
                    'lap_count': int(parts[7]),
                }
        except Exception as e:
            print("Admin parse error:", e)

    def read_message(self):
        """Returns the last received message and clears it."""
        msg = self.last_message
        self.last_message = None
        return msg

    def read_admin_response(self):
        """Returns the last admin state response and clears it."""
        resp = self.admin_response
        self.admin_response = None
        return resp

    def send(self, message_string):
        '''
        Sends a message string encoded as UTF-8
        '''
        formatted_data = message_string + ",\n"
        encoded_data = formatted_data.encode('utf-8')
        self.uart.write(encoded_data)
        # print("Sent UART: ", message_string)

    def send_admin_query(self):
        """Send A,query to request full state from motor controller."""
        self.send("A,query")

    def send_admin_start(self):
        """Send A,start to begin competition race timer."""
        self.send("A,start")

    def send_admin_lap(self, lap_number):
        """Send A,lap,N to report lap crossing."""
        self.send("A,lap,{}".format(lap_number))

    def send_admin_energy(self, energy_wh):
        """Send A,energy,Wh to sync energy value."""
        self.send("A,energy,{:.2f}".format(energy_wh))

    def send_admin_finish(self):
        """Send A,finish to end the race."""
        self.send("A,finish")
