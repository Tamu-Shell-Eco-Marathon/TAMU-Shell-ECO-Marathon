#pragma once

#include "hardware/uart.h"

void send_telemetry_uart();
void read_telemetry();
void parse_telemetry();

extern float target_speed;

extern char message_from_DIS[128]; // Assuming a max message length of 128 characters
extern char message_to_DIS[96];
extern int msg_len;
extern bool msg_ready;

// Race timer state
extern bool race_timer_running;
extern float race_elapsed_seconds;