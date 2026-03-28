#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "pico/stdlib.h"

// -----------------------------------------------------------------------------
// Runtime state / measurements (globals kept to preserve ISR behavior)
// -----------------------------------------------------------------------------

extern int adc_isense;
extern int adc_vsense;
extern int adc_throttle;

extern int adc_bias;
extern int duty_cycle;
extern int voltage_mv;
extern int phase_current_ma;
extern int current_target_ma;
extern int hall;
extern int test_current_ma;
extern int test_time_us;
extern uint motorState;
extern int fifo_level;
extern uint64_t ticks_since_init;

extern volatile int throttle; // 0-255, updated from ADC or serial

extern int motorstate_counter;
extern int prev_motorstate;
extern volatile float rpm;
extern float speed;
extern float prev_speed;
extern absolute_time_t rpm_time_start;
extern absolute_time_t rpm_time_end;

extern int phase_current_ma_smoothed;

extern bool smart_cruise;
extern int battery_current_ma;
extern int prev_current_target_ma;
extern absolute_time_t time_since_last_movement;
extern uint32_t motor_ticks;
extern bool at_target_speed;
extern bool UCO;
extern bool race_mode;
extern bool test_mode;
extern bool drive_mode;
extern bool comp_mode;
extern bool show_metrics;
extern float target_speed;
extern absolute_time_t time_since_at_target_speed;

// Competition / race timer state
extern bool race_timer_running;
extern absolute_time_t race_timer_start;
extern volatile float race_elapsed_seconds;
extern uint8_t comp_lap_count;
extern volatile float comp_energy_wh;

// Serial helpers (used by debug modes)
void check_serial_input(void);
void wait_for_serial_command(const char *message);
void increment_motor_ticks();
uint32_t get_motor_ticks();
void reset_motor_ticks();
void start_motor_ticks();
void stop_motor_ticks();
void get_RPM();
void check_serial();
bool read_serial_input();
void process_serial_input();

// Competition race timer
void start_race_timer(void);
void stop_race_timer(void);
void update_race_timer(void);
void update_comp_energy(float dt_seconds);
