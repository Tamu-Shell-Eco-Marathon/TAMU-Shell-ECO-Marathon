#include "motor_pins.h"

const uint LED_PIN = 25;
const uint AH_PIN = 16;
const uint AL_PIN = 17;
const uint BH_PIN = 18;
const uint BL_PIN = 19;
const uint CH_PIN = 20;
const uint CL_PIN = 21;
const uint HALL_1_PIN = 13;
const uint HALL_2_PIN = 14;
const uint HALL_3_PIN = 15;
const uint ISENSE_PIN = 26;
const uint VSENSE_PIN = 27;
const uint THROTTLE_PIN = 28;

const uint A_PWM_SLICE = 0;
const uint B_PWM_SLICE = 1;
const uint C_PWM_SLICE = 2;

const uint F_PWM = 16000;   // Desired PWM frequency
const uint FLAG_PIN = 2;
const uint HALL_OVERSAMPLE = 8;

const int DUTY_CYCLE_MAX = 65535;
const int CURRENT_SCALING = 3.3 / 0.0005 / 20 / 4096 * 1000;
const int VOLTAGE_SCALING = 3.3 / 4096 * (47 + 2.2) / 2.2 * 1000;
const int ADC_BIAS_OVERSAMPLE = 1000;
