#include "motor_user_config.h"
#include "motor_pins.h"

// Begin user config section ---------------------------

const bool IDENTIFY_HALLS_ON_BOOT = false;   // If true, controller will initialize the hall table by slowly spinning the motor
const bool IDENTIFY_HALLS_REVERSE = false;  // If true, will initialize the hall table to spin the motor backwards

int PHASE_MAX_CURRENT_MA = 90000;
int BATTERY_MAX_CURRENT_MA = 20000;

int THROTTLE_LOW = 800;
int THROTTLE_HIGH = 2000;

int ECO_CURRENT_ma = 12000;
float rpmtomph = 0.04767f; // Conversion from rpm to mph
float ticksPerMile = 174280.0f; // Hall state changes per mile — update at competition if needed
// Correct Hall Table !!!DO NOT CHANGE!!!
uint8_t hallToMotor[8] = {255, 3, 1, 2, 5, 4, 0, 255};

const bool CURRENT_CONTROL = true;          // Use current control or duty cycle control

const int CURRENT_CONTROL_LOOP_GAIN = 200;  // Adjusts the speed of the current control loop

const int HALL_IDENTIFY_DUTY_CYCLE = 25;

int UART_SEND_INTERVAL_US = 250000; // 4 Hz

//Smart cruise parameters
float cruise_error = 0.10f; //scalar for target speed band around effective target speed (e.g. 0.1 = +/- 10%)
int cruise_increment = 0; //miliamps added or subtracted when adjusting current target for smart cruise
float CRUISE_INCREMENT_MAX = 500;
float kp=64.0f;
float ki=0.0f;
float kd=0.0f;
float MAX_SMARTCRUISE_CURRENT_MA = 12000.0f; // mA ceiling for smart cruise current requests
float cruise_offset = 0.0f;                  // mph offset added to UART target speed

