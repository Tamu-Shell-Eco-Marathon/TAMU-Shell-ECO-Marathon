#include "motor_user_config.h"
#include "motor_pins.h"

// Begin user config section ---------------------------

const bool IDENTIFY_HALLS_ON_BOOT = false;   // If true, controller will initialize the hall table by slowly spinning the motor
const bool IDENTIFY_HALLS_REVERSE = false;  // If true, will initialize the hall table to spin the motor backwards

int LAUNCH_DUTY_CYCLE = 6553; // Duty cycle to use in launch mode. Can be set from 0 to DUTY_CYCLE_MAX, or 0-100 to specify a percentage of DUTY_CYCLE_MAX.
int PHASE_MAX_CURRENT_MA = 100000;
int BATTERY_MAX_CURRENT_MA = 30000;

int THROTTLE_LOW = 700;
int THROTTLE_HIGH = 2000;

int ECO_CURRENT_ma = 6000;
float rpmtomph = 0.04767f; // Conversion from rpm to mph
float launch_speed_mph = 1.43f; // Launch mode turns off above this vehicle speed

// Correct Hall Table !!!DO NOT CHANGE!!!
uint8_t hallToMotor[8] = {255, 3, 1, 2, 5, 4, 0, 255};

const bool CURRENT_CONTROL = true;          // Use current control or duty cycle control

const int CURRENT_CONTROL_LOOP_GAIN = 200;  // Adjusts the speed of the current control loop

const int HALL_IDENTIFY_DUTY_CYCLE = 25;

int UART_SEND_INTERVAL_US = 250000; // 4 Hz

//Smart cruise parameters
float cruise_error = 1.0f;
int cruise_increment = 1; //miliamps
float CRUISE_INCREMENT_MAX = 500;

// PID gains -- tune these in the field via serial commands kp/ki/kd.
// With PID output in mA and error in mph:
//   kp: immediate current per mph of error     (start: 1000 mA/mph)
//   ki: integral buildup per mph*second        (start: 500 mA/(mph*s))
//   kd: damping per mph/second rate of change  (start: 200 mA*s/mph)
float kp = 10.0f;
float ki =  5.0f;
float kd =  2.0f;

// How often the cruise PID recalculates.  50 Hz (20 ms) is well-matched to
// how quickly vehicle speed changes; running faster wastes CPU and makes
// derivative noise worse.
int   PID_UPDATE_INTERVAL_US = 20000;   // 50 Hz

// Anti-windup clamp on the integral accumulator.
// Set to BATTERY_MAX_CURRENT_MA / ki so the integrator alone can never
// command more than full current.  Adjust after setting ki.
float I_WINDUP_LIMIT = 60.0f;           // mA*s  (30000 mA / 500 mA/(mph*s) = 60 mph*s)

