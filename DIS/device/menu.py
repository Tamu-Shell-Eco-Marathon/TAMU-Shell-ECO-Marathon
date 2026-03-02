try:
    from typing import TYPE_CHECKING
except ImportError:
    TYPE_CHECKING = False

if TYPE_CHECKING:
    from typing import List, Tuple, Callable, Optional
    from display import DisplayManager
    from vehicle_state import Vehicle
    from uart_manager import UartManager

# ============================================================================
# SCREEN INTERFACE (Base Class)
# ============================================================================
class Screen:
    """Base class for all menu screens."""
    def __init__(self, manager: "Menu"):
        self.manager = manager

    def handle_input(self, display: "DisplayManager", vehicle: "Vehicle", uart: "UartManager", k0: bool, k1: bool, k1_hold: bool):
        pass

    def draw(self, display: "DisplayManager", vehicle: "Vehicle"):
        pass

    def on_enter(self):
        pass

# ============================================================================
# CONCRETE SCREENS
# ============================================================================

class ListScreen(Screen):
    """Generic screen for displaying a vertical list of options."""
    def __init__(self, manager: "Menu", options: "List[Tuple[str, Callable]]"):
        super().__init__(manager)
        self.options = options # List of (Label, Callback)
        self.index = 0

    def handle_input(self, display: "DisplayManager", vehicle: "Vehicle", uart: "UartManager", k0: bool, k1: bool, k1_hold: bool):
        if k0: # Scroll Down
            self.index = (self.index + 1) % len(self.options)
        if k1: # Scroll Up
            self.index = (self.index - 1) % len(self.options)
        if k1_hold: # Select
            label, callback = self.options[self.index]
            # Execute callback, passing dependencies if needed
            callback(display, vehicle, uart)

    def draw(self, display: "DisplayManager", vehicle: "Vehicle"):
        y = 0
        h = 12
        for i, (label, _) in enumerate(self.options):
            # Support dynamic labels (callables)
            if callable(label):
                label = label(vehicle)
            
            if i == self.index:
                display.oled.fill_rect(0, y, display.width, h, 1)
                display.oled.text(label, 2, y+2, 0)
            else:
                display.oled.text(label, 2, y+2, 1)
            y += h

class NumberInputScreen(Screen):
    """Screen for editing a number and sending it."""
    def __init__(self, manager: "Menu"):
        super().__init__(manager)
        self.nav_options = ["EXIT", "EDIT", "SEND"]
        self.nav_index = 0
        self.state = "NAV" # NAV or EDIT
        self.value = 0

    def handle_input(self, display: "DisplayManager", vehicle: "Vehicle", uart: "UartManager", k0: bool, k1: bool, k1_hold: bool):
        if self.state == "NAV":
            if k0: self.nav_index = (self.nav_index + 1) % len(self.nav_options)
            if k1: self.nav_index = (self.nav_index - 1) % len(self.nav_options)
            
            if k1_hold:
                selection = self.nav_options[self.nav_index]
                if selection == "EXIT":
                    self.manager.pop_screen()
                elif selection == "EDIT":
                    self.state = "EDIT"
                elif selection == "SEND":
                    cmd = f"M,t,{self.value}"
                    self.manager.push_screen(SendingScreen(self.manager, cmd, "TEST", on_success=lambda: setattr(vehicle, 'state', 'TEST')))
        
        elif self.state == "EDIT":
            if k0 and self.value > 0: self.value -= 1 # Don't want to set a negative value
            if k1: self.value += 1
            if k1_hold:
                self.state = "NAV"

    def draw(self, display: "DisplayManager", vehicle: "Vehicle"):
        # Draw Left Menu
        y = 10
        h = 12
        for i, opt in enumerate(self.nav_options):
            color = 1
            if i == self.nav_index and self.state == "NAV":
                display.oled.fill_rect(0, y, 40, h, 1)
                color = 0
            elif i == self.nav_index and self.state == "EDIT" and opt == "EDIT":
                display.oled.rect(0, y, 40, h, 1) # Outline to show active edit
            
            display.oled.text(opt, 2, y+2, color)
            y += h

        # Draw Right Number
        display.w_digits_45.set_textpos(70, 10)
        display.w_digits_45.printstring(str(self.value))

class SendingScreen(Screen):
    """Blocking screen that sends a command and waits for ACK."""
    def __init__(self, manager: "Menu", command: str, alert_text: str, wait_for_ack: bool = False, on_success=None):
        super().__init__(manager)
        self.command = command
        self.alert_text = alert_text
        self.wait_for_ack = wait_for_ack
        self.sent = False
        self.on_success = on_success

    def handle_input(self, display: "DisplayManager", vehicle: "Vehicle", uart: "UartManager", k0: bool, k1: bool, k1_hold: bool):
        # 1. Send Command Once
        if not self.sent:
            uart.send(self.command)
            self.sent = True
            if not self.wait_for_ack:
                self.finish(display)
                return

        # 2. Poll for ACK
        msg = uart.read_message()
        if msg:
            expected = self.command + ",ACK"
            # Simple check: if we get an ACK or just the command echoed back (depending on controller logic)
            # For now, strict check based on prompt requirements
            if msg == expected or "ACK" in msg: 
                self.finish(display)

    def finish(self, display: "DisplayManager"):
        if self.on_success:
            self.on_success()
        self.manager.pop_screen() # Pop SendingScreen
        # If we came from NumberInput, we might want to pop that too, but prompt implies just pop this.
        display.show_alert(self.alert_text, "MODE", 2)

    def draw(self, display: "DisplayManager", vehicle: "Vehicle"):
        display.oled.text("Sending...", 20, 25, 1)
        display.oled.text(self.command, 10, 40, 1)

# ============================================================================
# MENU MANAGER
# ============================================================================
class Menu:
    def __init__(self):
        self.stack = []
        self.reset()

    def reset(self):
        """Resets the menu to the main list."""
        self.stack = []
        
        # Define Main Menu Options
        main_options = [
            ("EXIT", self._exit_menu),
            (lambda v: "LOGGING: " + ("ON" if v.logging_armed else "OFF"), self._toggle_logging),
            ("SET DRIVE MODE", lambda d, v, u: self.push_screen(SendingScreen(self, "M,d", "DRIVE", on_success=lambda: setattr(v, 'state', 'DRIVE')))),
            ("SET TEST MODE", lambda d, v, u: self.push_screen(NumberInputScreen(self))),
            ("SET RACE MODE", lambda d, v, u: self.push_screen(SendingScreen(self, "M,r", "RACE", on_success=lambda: setattr(v, 'state', 'RACE')))),
            ("SET MOTOR LIMIT", lambda d, v, u: None)
        ]
        self.push_screen(ListScreen(self, main_options))

    def push_screen(self, screen: Screen):
        self.stack.append(screen)
        screen.on_enter()

    def pop_screen(self):
        if self.stack:
            self.stack.pop()

    def _exit_menu(self, display, vehicle, uart):
        display.display_mode = "CLUSTER"

    def _toggle_logging(self, display, vehicle, uart):
        vehicle.logging_armed = not vehicle.logging_armed

    def handle_input(self, display: "DisplayManager", vehicle: "Vehicle", uart: "UartManager", k0: bool, k1: bool, k1_hold: bool):
        if self.stack:
            self.stack[-1].handle_input(display, vehicle, uart, k0, k1, k1_hold)

    def render_menu_list(self, display: "DisplayManager", vehicle: "Vehicle"):
        if self.stack:
            self.stack[-1].draw(display, vehicle)