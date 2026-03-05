#include "UART.h"

#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/uart.h"
#include <string.h>
#include <stdlib.h>

#include "motor_state.h"
#include "motor_user_config.h"
#include "motor_pins.h"

#define MSG_MAX 128

char message_from_DIS[MSG_MAX];
char message_to_DIS[64];
int msg_len = 0;
bool msg_ready = false;
float target_speed = 15;

void send_telemetry_uart() {

    int duty_cycle_norm = duty_cycle * 100 / DUTY_CYCLE_MAX;
    int throttle_norm   = throttle * 100 / 255;

    UCO = (throttle_norm >= 90) ? 1 : 0;
    char signal = 's';
    int throttle_mapped = (throttle_norm*100)/90;
    if (throttle_mapped > 100) throttle_mapped = 100; //indicate UCO activated

    snprintf(message_to_DIS, sizeof(message_to_DIS), "%c,%d,%d,%f,%d,%d,%d,%d,%d\n",
             signal,
             motor_ticks,
             UCO,
             rpm*rpmtomph,
             voltage_mv,
             battery_current_ma,
             throttle_norm,
             throttle_mapped,
             duty_cycle_norm
             );

    uart_puts(UART_ID, message_to_DIS);
    //printf("Message to DIS: %s\n", message_to_DIS);
}

void read_telemetry(void) {
    while (uart_is_readable(UART_ID)) {
        char c = uart_getc(UART_ID);

        if (c == '\r') continue;

        if (c == '\n') {
            message_from_DIS[msg_len] = '\0';  // terminate string
            msg_ready = true;                  // mark message ready
            msg_len = 0;                       // reset for next message
            // printf("Message from DIS: %s\n", message_from_DIS);
            return;                            // stop after one full message
        }

        if (msg_len < MSG_MAX - 1) {
            message_from_DIS[msg_len++] = c;
        } else {
            msg_len = 0; // overflow protection
        }
    }
}


/* want to use message signifier for differently formated messages */

void send_acknowledgement() {            
    char ack_msg[MSG_MAX + 5];
    snprintf(ack_msg, sizeof(ack_msg), "%s,ACK\n", message_from_DIS);
    uart_puts(UART_ID, ack_msg);
}

void parse_telemetry(void) {
    if (!msg_ready) return;
    

    char *saveptr = NULL;
    char *tok = strtok_r(message_from_DIS, ",", &saveptr);

    const int max_index = 10;
    int index = 0;
    char *message[10];
    char mode;
    send_acknowledgement();

    while (tok != NULL && index < max_index) {
        message[index++] = tok;
        tok = strtok_r(NULL, ",", &saveptr);
    }

    if (index == 0) {      // no tokens
        msg_ready = false;
        return;
    }

    char signifier = message[0][0];  

   switch (signifier) {
    case 'T': // target speed
        target_speed = atof(message[1]);
        break;

    case 'M': // mode select
        mode = message[1][0];

        switch (mode) {
            case 'r':
                drive_mode = false;
                race_mode  = true;
                test_mode  = false;
                break;

            case 'd':
                drive_mode = true;
                race_mode  = false;
                test_mode  = false;
                break;

            case 't':
                drive_mode = false;
                race_mode  = false;
                test_mode  = true;
                test_current_ma = 1000*atoi(message[2]); // set test current
                break;

            default:
                // fallback mode if unknown
                drive_mode = true;
                race_mode  = false;
                test_mode  = false;
                break;
        }
        break; 
    //case 'temp'
    default:
        // unknown signifier
        break;
}

    msg_ready = false;
}