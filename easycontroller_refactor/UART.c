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
char message_to_DIS[96];
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
    char mode;
    if (comp_mode) mode = 'c';
    else if (race_mode) mode = 'r';
    else if (test_mode) mode = 't';
    else if (drive_mode) mode = 'd';
    else mode = 'u'; // unknown

    snprintf(message_to_DIS, sizeof(message_to_DIS), "%c,%d,%d,%.2f,%d,%d,%d,%d,%d,%c\n",
             signal,
             motor_ticks,
             UCO,
             rpm*rpmtomph,
             voltage_mv,
             battery_current_ma,
             throttle_norm,
             throttle_mapped,
             duty_cycle_norm,
             mode);

    uart_puts(UART_ID, message_to_DIS);
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

void send_admin_state(void) {
    // Respond to A,query with full competition state
    char mode_char;
    if (comp_mode) mode_char = 'c';
    else if (race_mode) mode_char = 'r';
    else if (test_mode) mode_char = 't';
    else if (drive_mode) mode_char = 'd';
    else mode_char = 'u';

    // Update elapsed time before sending
    update_race_timer();

    char buf[96];
    snprintf(buf, sizeof(buf), "A,state,%c,%d,%.1f,%u,%.2f,%d\n",
             mode_char,
             race_timer_running ? 1 : 0,
             race_elapsed_seconds,
             motor_ticks,
             comp_energy_wh,
             comp_lap_count);
    uart_puts(UART_ID, buf);
}

void parse_telemetry(void) {
    if (!msg_ready) return;

    // Save a copy before tokenizing (strtok_r modifies the string)
    char msg_copy[MSG_MAX];
    strncpy(msg_copy, message_from_DIS, MSG_MAX);
    msg_copy[MSG_MAX - 1] = '\0';

    char *saveptr = NULL;
    char *tok = strtok_r(message_from_DIS, ",", &saveptr);

    const int max_index = 10;
    int index = 0;
    char *message[10];
    char mode;

    while (tok != NULL && index < max_index) {
        message[index++] = tok;
        tok = strtok_r(NULL, ",", &saveptr);
    }

    if (index == 0) {      // no tokens
        msg_ready = false;
        return;
    }

    char signifier = message[0][0];

    // Send ACK for M and T commands (not A - A has its own responses)
    if (signifier == 'M' || signifier == 'T') {
        // Restore message_from_DIS for ACK (strtok_r destroyed it)
        strncpy(message_from_DIS, msg_copy, MSG_MAX);
        send_acknowledgement();
    }

   switch (signifier) {
    case 'T': // target speed
        if (index < 2) break;
        {
            float parsed_speed = atof(message[1]);
            if (parsed_speed >= 8.0f && parsed_speed <= 25.0f) {
                target_speed = parsed_speed;
            }
        }
        break;

    case 'M': // mode select
        if (index < 2) break;
        mode = message[1][0];

        switch (mode) {
            case 'c':
                drive_mode = false;
                race_mode  = false;
                test_mode  = false;
                comp_mode  = true;
                break;

            case 'r':
                drive_mode = false;
                race_mode  = true;
                test_mode  = false;
                comp_mode  = false;
                break;

            case 'd':
                drive_mode = true;
                race_mode  = false;
                test_mode  = false;
                comp_mode  = false;
                break;

            case 't':
                drive_mode = false;
                race_mode  = false;
                test_mode  = true;
                comp_mode  = false;
                if (index >= 3) {
                    test_current_ma = 1000*atoi(message[2]); // set test current
                }
                break;

            default:
                // fallback mode if unknown
                drive_mode = true;
                race_mode  = false;
                test_mode  = false;
                comp_mode  = false;
                break;
        }
        break;

    case 'A': // Administrative - competition state sync
        if (index < 2) break;

        if (strcmp(message[1], "query") == 0) {
            // DIS is asking for full state (e.g., after power loss recovery)
            send_admin_state();
        }
        else if (strcmp(message[1], "start") == 0) {
            // Start the competition race timer; reset ticks to 0
            start_race_timer();
            uart_puts(UART_ID, "A,start,ACK\n");
        }
        else if (strcmp(message[1], "lap") == 0) {
            // Record a lap crossing
            if (index >= 3) {
                int lap = atoi(message[2]);
                if (lap >= 1 && lap <= 4) {
                    comp_lap_count = (uint8_t)lap;
                }
            }
            uart_puts(UART_ID, "A,lap,ACK\n");
        }
        else if (strcmp(message[1], "energy") == 0) {
            // DIS syncing its more accurate energy value to MC
            if (index >= 3) {
                float synced_energy = atof(message[2]);
                if (synced_energy >= 0.0f) {
                    comp_energy_wh = synced_energy;
                }
            }
            uart_puts(UART_ID, "A,energy,ACK\n");
        }
        else if (strcmp(message[1], "finish") == 0) {
            // Race finished
            stop_race_timer();
            uart_puts(UART_ID, "A,finish,ACK\n");
        }
        break;

    default:
        // unknown signifier
        break;
}

    msg_ready = false;
}
