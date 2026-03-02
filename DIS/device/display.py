from writer import Writer
from fonts import font_digits_large, font_digits_med, font_letters_large, font_digits_45
import time
import framebuf
import hardware
from menu import Menu

class OLEDDriver(framebuf.FrameBuffer):
    def __init__(self):
        self.width = 128
        self.height = 64
        self.rotate = 180

        self.cs = hardware.oled_cs
        self.rst = hardware.oled_rst
        self.dc = hardware.oled_dc
        self.spi = hardware.spi
        
        # Initialize Pins
        self.cs(1)
        self.dc(1)

        self.buffer = bytearray(self.height * self.width // 8)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_HMSB)
        self.init_display()
        self._hw_invert = False

    def write_cmd(self, cmd):
        self.cs(1); self.dc(0); self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.cs(1); self.dc(1); self.cs(0)
        if isinstance(buf, int):
            self.spi.write(bytes([buf]))
        else:
            self.spi.write(buf)
        self.cs(1)

    def init_display(self):
        self.rst(1)
        time.sleep(0.001)
        self.rst(0)
        time.sleep(0.01)
        self.rst(1)
        
        self.write_cmd(0xAE) # turn off OLED display
        self.write_cmd(0x00) # set lower column address
        self.write_cmd(0x10) # set higher column address 
        self.write_cmd(0xB0) # set page address 
        self.write_cmd(0xdc) # set display start line 
        self.write_cmd(0x00) 
        self.write_cmd(0x81) # contract control 
        self.write_cmd(0x6f) # 128
        self.write_cmd(0x21) # Set Memory addressing mode
        if self.rotate == 0:
            self.write_cmd(0xa0)
        elif self.rotate == 180:
            self.write_cmd(0xa1)
        self.write_cmd(0xc0) # Com scan direction
        self.write_cmd(0xa4) # Disable Entire Display On
        self.write_cmd(0xa6) # normal / reverse
        self.write_cmd(0xa8) # multiplex ratio 
        self.write_cmd(0x3f) # duty = 1/64
        self.write_cmd(0xd3) # set display offset 
        self.write_cmd(0x60)
        self.write_cmd(0xd5) # set osc division 
        self.write_cmd(0x41)
        self.write_cmd(0xd9) # set pre-charge period
        self.write_cmd(0x22)   
        self.write_cmd(0xdb) # set vcomh 
        self.write_cmd(0x35)  
        self.write_cmd(0xad) # set charge pump enable 
        self.write_cmd(0x8a) # Set DC-DC enable
        self.write_cmd(0XAF)

    def show(self, invert=False):
        if invert != self._hw_invert:
            self.write_cmd(0xa7 if invert else 0xa6)
            self._hw_invert = invert

        self.write_cmd(0xB0)
        for page in range(0, 64):
            column = page if self.rotate == 180 else (63 - page)
            self.write_cmd(0x00 + (column & 0x0F))
            self.write_cmd(0x10 + (column >> 4))
            start_index = page * 16
            end_index = start_index + 16
            self.write_data(self.buffer[start_index:end_index])

class ButtonManager:
    def __init__(self):
        self.key0 = hardware.key0
        self.key1 = hardware.key1
        
        now = time.ticks_ms()
        self._debounce_ms = 150
        self._longpress_ms = 2000
        
        self._last_key0 = self.key0.value()
        self._last_key1 = self.key1.value()
        self._last_time_k0 = now
        self._last_time_k1 = now
        self._k1_press_start = None
        self._k1_reset_fired = False

    def check_events(self):
        now = time.ticks_ms()
        k0 = self.key0.value()
        k1 = self.key1.value()

        k0_press = False
        k1_press = False
        k1_long_press = False
        k1_long_release = False

        # KEY0 short press
        if self._last_key0 == 1 and k0 == 0:
            if time.ticks_diff(now, self._last_time_k0) > self._debounce_ms:
                k0_press = True
                self._last_time_k0 = now

        # KEY1 press start
        if self._last_key1 == 1 and k1 == 0:
            if time.ticks_diff(now, self._last_time_k1) > self._debounce_ms:
                self._k1_press_start = now
                self._k1_reset_fired = False

        # KEY1 long press detection
        if self._k1_press_start is not None and k1 == 0 and not self._k1_reset_fired:
            press_ms = time.ticks_diff(now, self._k1_press_start)
            if press_ms >= self._longpress_ms:
                k1_long_press = True
                self._k1_reset_fired = True

        # KEY1 release
        if self._last_key1 == 0 and k1 == 1 and self._k1_press_start is not None:
            press_ms = time.ticks_diff(now, self._k1_press_start)
            if not self._k1_reset_fired and press_ms < self._longpress_ms:
                k1_press = True
            if self._k1_reset_fired:
                k1_long_release = True
                self._k1_reset_fired = False
            self._k1_press_start = None
            self._last_time_k1 = now

        self._last_key0 = k0
        self._last_key1 = k1

        return k0_press, k1_press, k1_long_press, k1_long_release

    def update(self, vehicle, display, uart_manager):
        """
        Polls buttons and executes actions on the vehicle or display.
        """
        k0_click, k1_click, k1_hold, k1_hold_release = self.check_events()
        now = time.ticks_ms()

        # --- MENU MODE INPUTS ---
        if display.display_mode == "MENU":
            display.menu.handle_input(display, vehicle, uart_manager, k0_click, k1_click, k1_hold)
            return

        # --- CLUSTER MODE INPUTS ---
        if display.display_mode == "CLUSTER":
            if k1_click:
                if vehicle.timer_running:
                    vehicle._stored_elapsed_ticks += time.ticks_diff(now, vehicle._timer_start_ticks)
                    vehicle.timer_running = False
                    vehicle.timer_state = 'paused'
                else:
                    vehicle._timer_start_ticks = now
                    vehicle.timer_running = True
                    vehicle.timer_state = 'running'

            if k1_hold:
                if display.current_screen == 6:
                    display.display_mode = "MENU"
                    display.menu.reset()
                else:
                    vehicle._stored_elapsed_ticks = 0
                    vehicle.distance_miles = 0
                    vehicle.timer_running = False
                    vehicle.timer_state = 'reset'
                    vehicle._timer_start_ticks = now
                    display.show_alert("TIMER", "RESET", 2)

            if k0_click:
                display.change_screen(1)

class DisplayManager:
    def __init__(self, oled_driver: OLEDDriver):
        self.oled = oled_driver
        self.width = oled_driver.width
        self.height = oled_driver.height
        self.current_screen = 0
        self.num_screens = 7
        self.display_mode = "CLUSTER" # Cluster, Menu, Race
        
        # Menu System
        self.menu = Menu()

        # --- Custom Font Writers ----
        self.w_digits_large = Writer(self.oled, font_digits_large, verbose=False)
        self.w_digits_45 = Writer(self.oled, font_digits_45, verbose = False)
        self.w_digits_med = Writer(self.oled, font_digits_med, verbose=False)
        self.w_letters_big = Writer(self.oled, font_letters_large, verbose=False)

        # Gauge Configuration
        self.ANCHOR_X = 85
        self.DIGIT_Y = 0
        self.DOT_SIZE = 4
        self.DOT_PADDING = 3
        

        # ---- Precompute fixed slot positions for DD.D ---- # Remove when new version is done
        self._big_slot_x0 = 9  # tens
        self._big_slot_x1 = 43  # ones
        self._big_slot_xdot = 79  # '.'
        self._big_slot_x2 = 93  # tenths
        self._big_slot_y = 0

        # ---- Precompute fixed slot positions for MM:SS ----
        dmed = self.w_digits_med.stringlen("0")
        colon_w = self.w_digits_med.stringlen(":")
        x0m = -4
        self._time_x_m10 = x0m
        self._time_x_m1 = self._time_x_m10 + dmed - 4
        self._time_x_colon = self._time_x_m1 + dmed - 4
        self._time_x_s10 = self._time_x_colon + colon_w - 22
        self._time_x_s1 = self._time_x_s10 + dmed - 4
        self._time_y = 5

        #--------- Alert State ----------------
        self._msg_top = None
        self._msg_bottom = None
        self._msg_until = 0  # ms timestamp; 0 means no active message

    def change_screen(self, delta):
        self.current_screen = (self.current_screen + delta) % self.num_screens
        print(f"screen: {self.current_screen}")

    def update(self, vehicle, uart_manager):
        """
        Main Render Pipeline:
        1. Clear Buffer
        2. Render Content (Screen specific)
        3. Render Overlays (Status bar, Eco)
        4. Render Alerts (Priority)
        5. Present (Calculate inversion and show)
        """
        # 1. Clear
        self.oled.fill(0)

        # Check for Alerts (Priority)
        now = time.ticks_ms()
        alert_active = False
        if self._msg_top is not None:
            if time.ticks_diff(self._msg_until, now) > 0:
                alert_active = True
            else:
                self.clear_alert()

        if alert_active:
            self.render_alert(self._msg_top, self._msg_bottom)
        else:
            # 2. Render Content
            label = ""
            
            if self.display_mode == "MENU":
                self.menu.render_menu_list(self, vehicle)
            else:
                if self.current_screen == 0:
                    self.render_gauge(vehicle.motor_mph, precision=1)
                    label = "MPH"
                elif self.current_screen == 1:
                    self.render_time(vehicle.timer_elapsed_seconds)
                    label = "ELAPSED"
                elif self.current_screen == 2:
                    self.render_gauge(vehicle.current)
                    label = "AMPS"
                elif self.current_screen == 3:
                    self.render_gauge(vehicle.voltage)
                    label = "VOLTS"
                elif self.current_screen == 4:
                    self.render_demo_distance(vehicle.distance_miles)
                    label = "MILES"
                elif self.current_screen == 5:
                    self.render_gauge(vehicle.target_mph)
                    label = "TARGET"
                elif self.current_screen == 6:
                    self.render_menu_gate()

            # 3. Render Status Bar
            if self.current_screen < 6:
                self.render_status_bar(uart_manager.uart_blink, vehicle.timer_state, vehicle.logging_armed, label)
                self.oled.text(vehicle.state[:1], 0, 0, 1) ## DEBUG - show vehicle state in upper right corner

        # 5. Present
        invert = False
        self.oled.show(invert=invert)

    def render_gauge(self, value, precision=1):
        # Format the number - need absolute value
        abs_value = abs(value)
        # Format string based on precision
        full_str = "{:.{}f}".format(abs_value, precision)
        # Split number across the decimal place
        if "." in full_str:
            int_part, dec_part = full_str.split(".")
        else:
            int_part, dec_part = full_str, ""

        # --- 2. Draw Numbers ---
        # Draw the integer part
        char_width = self.w_digits_45.font.max_width()
        int_width = len(int_part) * char_width
        int_x = self.ANCHOR_X - self.DOT_PADDING - int_width
        
        self.w_digits_45.set_textpos(int_x, self.DIGIT_Y)
        self.w_digits_45.printstring(int_part)

        # Draw the decimal point if we have one
        if precision > 0:
            dot_y = self.w_digits_45.height - self.DOT_SIZE
            self.oled.ellipse(self.ANCHOR_X, dot_y, self.DOT_SIZE, self.DOT_SIZE, 1, 1)
            dec_x = self.ANCHOR_X + self.DOT_SIZE + self.DOT_PADDING
            self.w_digits_45.set_textpos(dec_x, self.DIGIT_Y)
            self.w_digits_45.printstring(dec_part)
        
        # Draw the negative sign manually
        if value < 0:
            minus_width = 10
            minus_x = int_x - minus_width - 4
            minus_y = 25
            self.oled.fill_rect(minus_x, minus_y, minus_width, 1)

    def render_time(self, seconds):
        """
        Draw elapsed time as MM:SS using the medium digit font.
        """
        if seconds < 0: seconds = 0
        total = int(seconds)

        max_total = 99 * 60 + 59
        if total > max_total: total = max_total

        mins = total // 60
        secs = total % 60

        m10 = mins // 10
        m1 = mins % 10
        s10 = secs // 10
        s1 = secs % 10

        y = self._time_y

        # Minutes (tens and ones)
        self.w_digits_med.set_textpos(self._time_x_m10, y)
        self.w_digits_med.printstring(str(m10))
        self.w_digits_med.set_textpos(self._time_x_m1, y)
        self.w_digits_med.printstring(str(m1))

        # Colon
        self.w_digits_med.set_textpos(self._time_x_colon, y - 7)
        self.w_digits_med.printstring(":")

        # Seconds (tens and ones)
        self.w_digits_med.set_textpos(self._time_x_s10, y)
        self.w_digits_med.printstring(str(s10))
        self.w_digits_med.set_textpos(self._time_x_s1, y)
        self.w_digits_med.printstring(str(s1))

    def render_demo_distance(self, distance):
        """Draw distance that caps at out .999 for demo purposes only"""
        distance = max(0, min(int(distance * 1000), 999))

        n1 = distance // 100
        n2 = (distance // 10) % 10
        n3 = distance % 10

        y = self._big_slot_y

        self.w_digits_large.set_textpos(0, y)
        self.w_digits_large.printstring(".")
        self.w_digits_large.set_textpos(14, y)
        self.w_digits_large.printstring(str(n1))
        self.w_digits_large.set_textpos(53, y)
        self.w_digits_large.printstring(str(n2))
        self.w_digits_large.set_textpos(91, y)
        self.w_digits_large.printstring(str(n3))

    def render_status_bar(self, uart_blink, timer_state, logging_armed, label_text=None):
        """
        Draw UART and timer indicators on the bottom row.
        """
        y = self.height - 8

        if uart_blink:
            self.oled.text("U", 0, y, 1)

        x_rec = 10
        if timer_state == "running":
            self.oled.fill_rect(x_rec - 1, y - 1, 25, 10, 1)
            if logging_armed:
                self.oled.text("LOG", x_rec, y, 0)
            else:
                self.oled.text("REC", x_rec, y, 0)
        elif timer_state == "paused":
            if logging_armed:
                self.oled.text("LOG", x_rec, y, 1)
            else:
                self.oled.text("REC", x_rec, y, 1)
        elif timer_state == "reset" and logging_armed:
            self.oled.text("LOG", x_rec, y, 1)

        if label_text:
            label_x = self.width - len(label_text) * 8
            self.oled.text(label_text, label_x, y, 1)

    def render_alert(self, top, bottom):
        """
        Draw two words in the letter font, centered.
        """
        if top:
            top = top.upper()
            x_top = max(0, (self.width - self.w_letters_big.stringlen(top)) // 2)
            self.w_letters_big.set_textpos(x_top, 0)
            self.w_letters_big.printstring(top)
        if bottom:
            bottom = bottom.upper()
            x_bottom = max(0, (self.width - self.w_letters_big.stringlen(bottom)) // 2)
            self.w_letters_big.set_textpos(x_bottom, 24)
            self.w_letters_big.printstring(bottom)

    def show_alert(self, top, bottom, seconds):
        """
        Schedule an alert for a certain amount of seconds.
        """
        ms = int(seconds * 1000)
        now = time.ticks_ms()
        self._msg_top = top
        self._msg_bottom = bottom
        self._msg_until = time.ticks_add(now, ms)
        print(f"Alert: {top or ''} {bottom or ''}")

    def clear_alert(self):
        """Clear any active alert immediately."""
        self._msg_top = None
        self._msg_bottom = None
        self._msg_until = 0

    def center_text_x(self, text):
        return int((self.width - (len(text) * 8)) / 2)

    def render_menu_gate(self):
        text1 = "PRESS AND HOLD"
        text2 = "TO ENTER MENU"
        self.oled.text(text1, self.center_text_x(text1), 5, 1)
        self.oled.text(text2, self.center_text_x(text2), 15, 1)
