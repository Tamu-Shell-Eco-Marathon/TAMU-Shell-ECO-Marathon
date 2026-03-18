#include <stdio.h>
#include <stdlib.h>

#include "pico/stdlib.h"
#include "hardware/uart.h"
#include "hardware/pwm.h"

#include "motor_user_config.h"
#include "motor_pins.h"
#include "motor_state.h"
#include "motor_hw.h"
#include "motor_control.h"
#include "UART.h"


int main(void) {
    printf("Hello from Pico!\n");
    init_hardware();
    stdio_init_all(); //debug, remove this when you dont need USB serial communication 

    // UART init
    uart_init(UART_ID, BAUD_RATE);
    gpio_set_function(TX_PIN, GPIO_FUNC_UART);
    gpio_set_function(RX_PIN, GPIO_FUNC_UART);

    printf("Hello from Pico!\n");


    if (IDENTIFY_HALLS_ON_BOOT) {
        identify_halls();
        wait_for_serial_command("Hall identification done. Review table above.");
    }

    sleep_ms(1000);

    // Enables interrupts, starting motor commutation (unchanged)
    pwm_set_irq_enabled(A_PWM_SLICE, true);

    absolute_time_t last_UART_send = get_absolute_time();


    while (true) {
        //gpio_put(LED_PIN, !gpio_get(LED_PIN));
        //check_serial_input_for_Phase_Current();


        if (absolute_time_diff_us(last_UART_send, get_absolute_time()) >= UART_SEND_INTERVAL_US) {
            send_telemetry_uart();
            read_telemetry();
            parse_telemetry();
            process_serial_input();
            last_UART_send = get_absolute_time();

            if (show_metrics){
                printf("Mode: %s\n", drive_mode ? "Drive" : (race_mode ? "Race" : "Test"));
                printf("Battery Voltage: %.2f V\n", voltage_mv / 1000.0f);
                if (race_mode){
                    printf("Speed: %f mph\n", rpm * rpmtomph);
                    printf("Target Speed: %f mph\n", target_speed);
                    printf("Target Current: %d mA\n", current_target_ma);
                    printf("Battery Current: %d mA\n", battery_current_ma);
                    printf("Phase Current: %d mA\n", phase_current_ma_smoothed);
                    printf("\n");
                }
                if (drive_mode){
                    printf("Speed: %f mph\n", rpm * rpmtomph);
                    printf("Target Current: %d mA\n", current_target_ma);
                    printf("Battery Current: %d mA\n", battery_current_ma);
                    printf("Phase Current: %d mA\n", phase_current_ma_smoothed);
                    printf("\n");
                }
                if (test_mode){
                    printf("Test Current: %d mA\n", test_current_ma);
                    printf("Current Target: %d mA\n", current_target_ma);
                    printf("Battery Current: %d mA\n", battery_current_ma);
                    printf("Phase Current: %d mA\n", phase_current_ma_smoothed);
                    printf("Speed: %f mph\n", rpm * rpmtomph);
                    printf("UCO: %s\n", UCO ? "ON" : "OFF");
                    printf("\n");
                }
             }
            gpio_put(LED_PIN, !gpio_get(LED_PIN));
        }
    }

    return 0;
}


//test
