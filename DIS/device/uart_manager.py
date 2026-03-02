class UartManager:
    def __init__(self, uart_instance):
        self.uart = uart_instance
        self.buffer = ""

        self.uart_blink = False
        self.new_data = False # Flag to indicate if new data was parsed
        self.last_message = None # Store last message for polling

    def update(self, vehicle):
        """
        Reads from UART, parses messages, and updates internal state.
        Should be called once per main loop iteration.
        """
        self.new_data = False
        if self.uart.any():
            data = self.uart.read()
            if data:
                # Convert bytes to printable characters
                for b in data:
                    if 32 <= b <= 126 or b == 10:
                        self.buffer += chr(b)

                # Process complete lines
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    line = line.strip()
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
                if len(parts) >= 9:
                    vehicle.motor_ticks = int(parts[1])
                    vehicle.eco = bool(int(parts[2]))
                    vehicle.motor_mph = float(parts[3])
                    vehicle.rpm = int(vehicle.motor_mph / 0.04767) # Back-calculate RPM for physics consistency
                    vehicle.voltage = int(parts[4]) / 1000.0
                    vehicle.current = int(parts[5]) / 1000.0
                    vehicle.throttle_position = int(parts[6])
                    vehicle.throttle = int(parts[7])
                    vehicle.duty_cycle = int(parts[8])
        except Exception as e:
            print("Parse error:", e, "on line:", line)

    def read_message(self):
        """Returns the last received message and clears it."""
        msg = self.last_message
        self.last_message = None
        return msg
    
    def send(self, message_string):
        '''
        Sends a message string encoded as UTF-8
        '''
        # Format the data by adding a newline character
        formatted_data = message_string + ",\n"

        # Encode as UTF-8
        encoded_data = formatted_data.encode('utf-8')

        # Send the message over UART
        self.uart.write(encoded_data)

        #### DEBUG
        print("Sent UART: ", message_string)
