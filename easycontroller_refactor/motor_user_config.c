#include "motor_user_config.h"
#include "motor_pins.h"

// Begin user config section ---------------------------

const bool IDENTIFY_HALLS_ON_BOOT = false;   // If true, controller will initialize the hall table by slowly spinning the motor
const bool IDENTIFY_HALLS_REVERSE = false;  // If true, will initialize the hall table to spin the motor backwards

int PHASE_MAX_CURRENT_MA = 90000;
int BATTERY_MAX_CURRENT_MA = 20000;

int THROTTLE_LOW = 700;
int THROTTLE_HIGH = 2000;

int ECO_CURRENT_ma = 6000;
float rpmtomph = 0.04767f; // Conversion from rpm to mph

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
float kp=32.0f;
float ki=0.0f;
float kd=0.0f;

