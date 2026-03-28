#pragma once

#include <stdint.h>
#include <stdbool.h>

// -----------------------------------------------------------------------------
// User-configurable settings
// -----------------------------------------------------------------------------

extern const bool IDENTIFY_HALLS_ON_BOOT;   // If true, controller will initialize the hall table by slowly spinning the motor
extern const bool IDENTIFY_HALLS_REVERSE;  // If true, will initialize the hall table to spin the motor backwards
extern const bool COMPUTER_CONTROL;        // If true will enable throttle control via serial communication

extern int PHASE_MAX_CURRENT_MA;
extern int BATTERY_MAX_CURRENT_MA;
extern int THROTTLE_LOW;
extern int THROTTLE_HIGH;
extern int ECO_CURRENT_ma;
extern float rpmtomph;                    // Conversion from rpm to mph

extern uint8_t hallToMotor[8];            // Hall-to-commutation-state table (DO NOT CHANGE TABLE VALUES)

extern const bool CURRENT_CONTROL;        // Use current control or duty cycle control
extern const int CURRENT_CONTROL_LOOP_GAIN;

extern const int HALL_IDENTIFY_DUTY_CYCLE;

extern int UART_SEND_INTERVAL_US;
//Smart cruise parameters
extern float cruise_error;
extern float cruise_increment;
extern float CRUISE_INCREMENT_MAX;
extern float kp;
extern float ki;
extern float kd;
extern int CRUISE_MAX_CURRENT_MA;  // Max current smart cruise can request (mA)
extern float target_speed_adjustment_factor; // Additive offset to DIS target speed (mph), default 0
