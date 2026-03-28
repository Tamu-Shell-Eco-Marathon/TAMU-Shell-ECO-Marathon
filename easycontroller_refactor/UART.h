#pragma once

#include "hardware/uart.h"

void send_telemetry_uart(void);
void read_telemetry(void);
void parse_telemetry(void);
void send_admin_state(void);

extern float target_speed;

extern char message_from_DIS[128];
extern char message_to_DIS[96];
extern int msg_len;
extern bool msg_ready;