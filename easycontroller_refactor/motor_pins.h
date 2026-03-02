#pragma once

#include "pico/stdlib.h"

// -----------------------------------------------------------------------------
// Pinout & low-level constants & UART definitions
// -----------------------------------------------------------------------------

extern const uint LED_PIN;
extern const uint AH_PIN;
extern const uint AL_PIN;
extern const uint BH_PIN;
extern const uint BL_PIN;
extern const uint CH_PIN;
extern const uint CL_PIN;

extern const uint HALL_1_PIN;
extern const uint HALL_2_PIN;
extern const uint HALL_3_PIN;

extern const uint ISENSE_PIN;
extern const uint VSENSE_PIN;
extern const uint THROTTLE_PIN;

extern const uint A_PWM_SLICE;
extern const uint B_PWM_SLICE;
extern const uint C_PWM_SLICE;

extern const uint F_PWM;
extern const uint FLAG_PIN;
extern const uint HALL_OVERSAMPLE;

extern const int DUTY_CYCLE_MAX;
extern const int CURRENT_SCALING;
extern const int VOLTAGE_SCALING;
extern const int ADC_BIAS_OVERSAMPLE;

// UART COMs
#define UART_ID   uart1
#define TX_PIN    4
#define RX_PIN    5
#define BAUD_RATE 115200