#include "motor_state.h"
#include "motor_user_config.h"
#include "motor_pins.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pico/stdlib.h"
#include "pico/bootrom.h"

#define MAX_MSG_LEN 128
#define MAX_TOKENS 5

int adc_isense = 0;
int adc_vsense = 0;
int adc_throttle = 0;

int adc_bias = 0;
int duty_cycle = 0;
int voltage_mv = 0;
int phase_current_ma = 0;
int current_target_ma = 0;
int hall = 0;
int test_current_ma = 1000; 
int test_time_us = 5000000; // 5 seconds
uint motorState = 0;
int fifo_level = 0;
uint64_t ticks_since_init = 0;

volatile int throttle = 0;  // 0-255

int motorstate_counter = 0;
int prev_motorstate = 0;
volatile float rpm = 0.0f;
float speed;
float prev_speed;
absolute_time_t rpm_time_start = 0;
absolute_time_t rpm_time_end = 0;

int phase_current_ma_smoothed = 0;

bool smart_cruise = false;
bool record_motor_ticks = false;
int battery_current_ma = 0;
int prev_current_target_ma = 0;
absolute_time_t time_since_last_movement = 0;
uint32_t motor_ticks = 0;
bool UCO = false;
bool at_target_speed = false;
bool race_mode = true;
bool test_mode = false;
bool drive_mode = false;
bool comp_mode = false;
absolute_time_t time_since_at_target_speed = 0;

// Competition / race timer state
bool race_timer_running = false;
absolute_time_t race_timer_start = 0;
volatile float race_elapsed_seconds = 0.0f;
uint8_t comp_lap_count = 0;
volatile float comp_energy_wh = 0.0f;



void wait_for_serial_command(const char *message) {
    printf("%s\n", message);
    printf("Type any key + Enter to continue...\n");

    int c = getchar();
    (void)c;
}



void check_serial_input(void) {
    static char buf[8];
    static int idx = 0;

    int c;
    while ((c = getchar_timeout_us(0)) != PICO_ERROR_TIMEOUT) {
        if (c == '\n' || c == '\r') {
            if (idx > 0) {
                buf[idx] = '\0';
                int val = atoi(buf);
                if (val >= 0 && val <= 255) {
                    throttle = val;
                    printf("Throttle updated: %d\n", throttle);
                }
                idx = 0;
            }
        } else if (idx < (int)(sizeof(buf) - 1)) {
            buf[idx++] = (char)c;
        }
    }
}

void increment_motor_ticks() {
    motor_ticks++;
}
uint32_t get_motor_ticks() {
    return motor_ticks;
}
void reset_motor_ticks() {
    motor_ticks = 0;
}
void start_motor_ticks() {
    record_motor_ticks = true;
}
void stop_motor_ticks() {
    record_motor_ticks = false;
}

void get_RPM(){
    if (motorstate_counter == 0) {
        rpm_time_start = get_absolute_time();
    }

    if (motorState != prev_motorstate) {
        time_since_last_movement = get_absolute_time();
        motorstate_counter += 1;
        increment_motor_ticks();
    }

    if (motorstate_counter >= 10) {
        rpm_time_end = get_absolute_time();
        float dt_us = (float)absolute_time_diff_us(rpm_time_start, rpm_time_end);
        rpm = (motorstate_counter * 60.0f * 1e6f) / (dt_us * 138.0f); // 138 motor ticks in one rotation
        motorstate_counter = 0;
    }

    if (absolute_time_diff_us(time_since_last_movement, get_absolute_time()) > 500000) { // resets rpm counter if no motor movement for .5 seconds
        rpm = 0;
        motorstate_counter = 0;
    }
}


void enter_bootloader(void) {
    reset_usb_boot(0, 0); // jumps to BOOTSEL without unplugging
}

// Global or static variables to persist between function calls
char input_buffer[MAX_MSG_LEN];
int buffer_idx = 0;
char *tokens[MAX_TOKENS];
int token_count = 0;

/**
 * Non-blocking function to read serial and tokenize by comma
 * Returns true if a full message was processed, false otherwise.
 */

 // Keep your global variables as they are
// input_buffer, buffer_idx, tokens, token_count, etc.

bool read_serial_input() {
    while (true) {
        int c = getchar_timeout_us(0); // Non-blocking read

        if (c == PICO_ERROR_TIMEOUT) {
            return false; // SILENTLY return. Do not print here!
        }

        // --- DEBUG: Uncomment this ONLY if you suspect hardware issues ---
        // printf("Debug Char: %c (%d)\n", c, c); 
        // ----------------------------------------------------------------

        // Check for end of line (Enter key)
        if (c == '\n' || c == '\r') {
            if (buffer_idx > 0) { // Only process if we have data
                input_buffer[buffer_idx] = '\0'; // Seal the string

                // Tokenize the string
                token_count = 0;
                char *token = strtok(input_buffer, ",");
                while (token != NULL && token_count < MAX_TOKENS) {
                    tokens[token_count++] = token;
                    token = strtok(NULL, ",");
                }

                buffer_idx = 0; // Reset for next message
                return true;    // MESSAGE READY!
            }
            else {
                // Ignore empty enter key presses
                buffer_idx = 0;
                continue; 
            }
        } 
        else {
            // Store character if there is space
            if (buffer_idx < MAX_MSG_LEN - 1) {
                // Optional: Only allow valid characters to keep buffer clean
                if(c >= 32 && c <= 126) { 
                    input_buffer[buffer_idx++] = (char)c;
                }
            }
        }
    }
}

bool show_metrics = false; // Set to true to enable printing of metrics in process_serial_input (for debugging)

typedef enum {
    CMD_FUNC, 
    CMD_FLOAT,
    CMD_INT,  
    CMD_TOGGLE
} CmdType;


typedef struct {
    const char* name;
    CmdType type;
    void* target;      
} Command;


// New commands entered here
const Command cmd_table[] = {
    {"BOOT",                   CMD_FUNC,   (void*)enter_bootloader},
    {"kp",                     CMD_FLOAT,  (void*)&kp},
    {"ki",                     CMD_FLOAT,  (void*)&ki},
    {"kd",                     CMD_FLOAT,  (void*)&kd},
    {"BATTERY_MAX_CURRENT_MA", CMD_INT,    (void*)&BATTERY_MAX_CURRENT_MA},
    {"PHASE_MAX_CURRENT_MA",   CMD_INT,    (void*)&PHASE_MAX_CURRENT_MA},
    {"cruise_error",           CMD_INT,    (void*)&cruise_error},
    {"test_current_ma",        CMD_INT,    (void*)&test_current_ma},
    {"CRUISE_MAX_CURRENT_MA",           CMD_INT,    (void*)&CRUISE_MAX_CURRENT_MA},
    {"target_speed_adjustment_factor", CMD_FLOAT,  (void*)&target_speed_adjustment_factor},
    {"show_metrics",                   CMD_TOGGLE, (void*)&show_metrics}
};

const int NUM_CMDS = sizeof(cmd_table) / sizeof(cmd_table[0]);

void process_serial_input() {
    if (!read_serial_input()) {
        return; 
    }

    printf(">>> Processing Command: [%s]\n", tokens[0]);

    if (strcmp(tokens[0], "help") == 0) {
        printf(">>> Commands: ");
        for (int i = 0; i < NUM_CMDS; i++) {
            printf("%s, ", cmd_table[i].name);
        }
        printf("help\n");
        return;
    }

    for (int i = 0; i < NUM_CMDS; i++) {
        if (strcmp(tokens[0], cmd_table[i].name) == 0) {
            
            if ((cmd_table[i].type == CMD_FLOAT || cmd_table[i].type == CMD_INT) && tokens[1] == NULL) {
                printf(">>> Error: Command '%s' requires a value.\n", tokens[0]);
                return;
            }

            switch (cmd_table[i].type) {
                case CMD_FUNC:
                    printf(">>> Executing %s...\n", cmd_table[i].name);
                    ((void (*)(void))cmd_table[i].target)(); 
                    break;
                
                case CMD_FLOAT: {
                    float* val = (float*)cmd_table[i].target;
                    *val = strtof(tokens[1], NULL);
                    printf(">>> %s updated to: %.4f\n", cmd_table[i].name, *val);
                    break;
                }
                
                case CMD_INT: {
                    int* val = (int*)cmd_table[i].target;
                    int raw = (int)strtof(tokens[1], NULL);
                    *val = raw;
                    printf(">>> %s updated to: %d\n", cmd_table[i].name, *val);
                    break;
                }
                
                case CMD_TOGGLE: {
                    bool* val = (bool*)cmd_table[i].target;
                    *val = !(*val); // Invert current state
                    printf(">>> %s: %s\n", cmd_table[i].name, *val ? "ON" : "OFF");
                    break;
                }
            }
            return;
        }
    }

    printf(">>> Unknown command: %s\n", tokens[0]);
    printf(">>> Type 'help' for a list of commands.\n");
}

// ---- Competition Race Timer Functions ----

void start_race_timer(void) {
    reset_motor_ticks();
    race_timer_running = true;
    race_timer_start = get_absolute_time();
    race_elapsed_seconds = 0.0f;
    comp_energy_wh = 0.0f;
    comp_lap_count = 0;
}

void stop_race_timer(void) {
    // Capture final elapsed time before stopping
    if (race_timer_running) {
        race_elapsed_seconds = absolute_time_diff_us(race_timer_start, get_absolute_time()) / 1e6f;
    }
    race_timer_running = false;
}

void update_race_timer(void) {
    if (race_timer_running) {
        race_elapsed_seconds = absolute_time_diff_us(race_timer_start, get_absolute_time()) / 1e6f;
    }
}

void update_comp_energy(float dt_seconds) {
    if (race_timer_running && dt_seconds > 0.0f) {
        float power_w = (voltage_mv / 1000.0f) * (battery_current_ma / 1000.0f);
        comp_energy_wh += power_w * (dt_seconds / 3600.0f);
    }
}
