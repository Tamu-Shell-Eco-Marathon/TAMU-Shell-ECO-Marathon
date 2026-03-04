import utime as time

class PerformanceMonitor:
    """A simple class to monitor and report performance metrics."""
    def __init__(self, print_interval_ms=5000, verbose=False):
        self.print_interval_ms = print_interval_ms
        self.verbose = verbose
        self.last_perf_print_ms = time.ticks_ms()
        self.draw_start_us = 0
        self.loop_start_us = 0

        self.total_draw_time_us = 0
        self.total_loop_time_us = 0
        self.draw_count = 0

    def loop_start(self):
        """Mark the start of a main loop iteration."""
        self.loop_start_us = time.ticks_us()

    def loop_stop(self):
        """Mark the end of a main loop iteration."""
        self.total_loop_time_us += time.ticks_diff(time.ticks_us(), self.loop_start_us)

    def start(self):
        """Start the timer for a display draw measurement."""
        self.draw_start_us = time.ticks_us()

    def stop(self):
        """Stop the display draw timer and record the measurement."""
        self.total_draw_time_us += time.ticks_diff(time.ticks_us(), self.draw_start_us)
        self.draw_count += 1

    def update(self, remaining_time=None, remaining_dist=None):
        """Check if it's time to print stats and do so if needed."""
        if time.ticks_diff(time.ticks_ms(), self.last_perf_print_ms) > self.print_interval_ms:
            self.last_perf_print_ms = time.ticks_ms()

            log_parts = []

            # Add verbose part if enabled and data is available
            if self.verbose and remaining_time is not None and remaining_dist is not None:
                verbose_str = f"rem_t: {remaining_time:.0f}s, rem_d: {remaining_dist:.3f}mi"
                log_parts.append(verbose_str)

            # Always add performance part
            n = self.draw_count if self.draw_count > 0 else 1
            avg_loop_us = self.total_loop_time_us / n
            avg_draw_us = self.total_draw_time_us / n
            perf_str = f"Loop: {avg_loop_us:.0f}us | Draw: {avg_draw_us:.0f}us (n={self.draw_count})"
            log_parts.append(perf_str)

            # Print the combined log line
            print(" | ".join(log_parts))

            # Reset for the next interval
            self.total_loop_time_us = 0
            self.total_draw_time_us = 0
            self.draw_count = 0