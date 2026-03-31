#!/usr/bin/env python3
"""
stage_control.py — Motorized XY stage control for Raspberry Pi.
Supports generic stepper-based stages (PT-XY100 style + most cheap microscope stages).

Wiring (change GPIO pins below to match your driver board):
    X axis: STEP → GPIO17  DIR → GPIO27  EN → GPIO22
    Y axis: STEP → GPIO23  DIR → GPIO24  EN → GPIO25
    Limit switches (optional): X → GPIO5  Y → GPIO6  (active LOW, pull-up enabled)

Driver: A4988 or DRV8825 recommended. Set microstepping on the driver board.
    Typical: 1/16 microstepping + 200-step motor + 2mm leadscrew = 1600 steps/mm
    Adjust STEPS_PER_MM to match your hardware.

Usage:
    from stage_control import Stage
    stage = Stage()
    stage.home()
    stage.move_to(10, 5)   # move to X=10mm Y=5mm
    stage.cleanup()
"""

import time

try:
    import RPi.GPIO as GPIO
    _GPIO_AVAILABLE = True
except ImportError:
    _GPIO_AVAILABLE = False

# --- Default GPIO pin assignments (BCM numbering) ---
X_STEP_PIN = 17
X_DIR_PIN  = 27
X_EN_PIN   = 22
Y_STEP_PIN = 23
Y_DIR_PIN  = 24
Y_EN_PIN   = 25
X_LIMIT_PIN = 5    # optional — set to None to disable
Y_LIMIT_PIN = 6    # optional — set to None to disable

# --- Stage mechanics (tune for your hardware) ---
STEPS_PER_MM   = 80     # steps per mm of travel
STEP_DELAY_S   = 0.0005 # seconds per half-step (controls speed; lower = faster)
HOME_STEP_DELAY = 0.001  # slower during homing for reliability


class Stage:
    """
    Controls a two-axis stepper stage.

    Args:
        steps_per_mm: Motor steps per mm of travel (tune for your hardware).
        step_delay:   Seconds between step pulses (lower = faster).
        x_step, x_dir, x_en: GPIO pins for X axis.
        y_step, y_dir, y_en: GPIO pins for Y axis.
        x_limit, y_limit:    GPIO pins for limit switches (None = no switch).
        simulate:            If True, print moves instead of driving GPIO.
                             Useful for testing without hardware attached.
    """

    def __init__(
        self,
        steps_per_mm=STEPS_PER_MM,
        step_delay=STEP_DELAY_S,
        x_step=X_STEP_PIN, x_dir=X_DIR_PIN, x_en=X_EN_PIN,
        y_step=Y_STEP_PIN, y_dir=Y_DIR_PIN, y_en=Y_EN_PIN,
        x_limit=X_LIMIT_PIN, y_limit=Y_LIMIT_PIN,
        simulate=False,
    ):
        self.steps_per_mm = steps_per_mm
        self.step_delay = step_delay
        self.simulate = simulate or not _GPIO_AVAILABLE

        self._pins = {
            'x_step': x_step, 'x_dir': x_dir, 'x_en': x_en,
            'y_step': y_step, 'y_dir': y_dir, 'y_en': y_en,
        }
        self._limits = {'x': x_limit, 'y': y_limit}

        self.x = 0.0  # current position mm
        self.y = 0.0

        if not self.simulate:
            self._setup_gpio()
        else:
            print("[stage] Simulation mode — no GPIO output")

    # ------------------------------------------------------------------
    # GPIO setup
    # ------------------------------------------------------------------

    def _setup_gpio(self):
        GPIO.setmode(GPIO.BCM)
        for pin in self._pins.values():
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        for pin_name, pin in self._limits.items():
            if pin is not None:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # Enable drivers (active LOW)
        GPIO.output(self._pins['x_en'], GPIO.LOW)
        GPIO.output(self._pins['y_en'], GPIO.LOW)

    # ------------------------------------------------------------------
    # Low-level stepping
    # ------------------------------------------------------------------

    def _pulse(self, step_pin, n_steps, delay=None):
        if delay is None:
            delay = self.step_delay
        if self.simulate:
            return
        for _ in range(n_steps):
            GPIO.output(step_pin, GPIO.HIGH)
            time.sleep(delay)
            GPIO.output(step_pin, GPIO.LOW)
            time.sleep(delay)

    def _set_dir(self, axis, positive):
        if self.simulate:
            return
        GPIO.output(
            self._pins[f'{axis}_dir'],
            GPIO.HIGH if positive else GPIO.LOW,
        )

    def _limit_hit(self, axis):
        pin = self._limits.get(axis)
        if pin is None or self.simulate:
            return False
        return not GPIO.input(pin)  # active LOW

    # ------------------------------------------------------------------
    # Public movement API
    # ------------------------------------------------------------------

    def move(self, dx=0.0, dy=0.0):
        """Move relative to current position (mm). Blocks until complete."""
        for axis, delta, attr in [('x', dx, 'x'), ('y', dy, 'y')]:
            if delta == 0:
                continue
            steps = round(abs(delta) * self.steps_per_mm)
            self._set_dir(axis, delta > 0)
            if self.simulate:
                print(f"[stage] {axis.upper()} {'+'if delta>0 else ''}{delta:.3f} mm ({steps} steps)")
            self._pulse(self._pins[f'{axis}_step'], steps)
            setattr(self, attr, getattr(self, attr) + delta)

    def move_to(self, x=None, y=None):
        """Move to absolute position (mm). Pass None to leave an axis unchanged."""
        dx = (x - self.x) if x is not None else 0.0
        dy = (y - self.y) if y is not None else 0.0
        self.move(dx, dy)

    def home(self, axes=None):
        """
        Home one or both axes using limit switches.

        Args:
            axes: 'x', 'y', or None to home both.
        Raises:
            RuntimeError if limit switch not configured for requested axis.
        """
        targets = ['x', 'y'] if axes is None else [axes]
        for ax in targets:
            if self._limits[ax] is None:
                raise RuntimeError(
                    f"No limit switch configured for {ax.upper()} axis. "
                    f"Pass x_limit / y_limit pin to Stage() or home manually."
                )
            print(f"[stage] Homing {ax.upper()}...")
            self._set_dir(ax, False)  # move toward home (negative direction)
            if not self.simulate:
                while not self._limit_hit(ax):
                    self._pulse(self._pins[f'{ax}_step'], 1, HOME_STEP_DELAY)
            setattr(self, ax, 0.0)
            print(f"[stage] {ax.upper()} at home.")

    def raster_scan(self, width_mm, height_mm, step_mm, start_x=0.0, start_y=0.0):
        """
        Generator that yields (x_mm, y_mm) positions for a boustrophedon
        (snake-path) raster scan. Move the stage and capture at each position.

        Example:
            for x, y in stage.raster_scan(20, 20, 0.5):
                stage.move_to(x, y)
                capture_image(x, y)

        Args:
            width_mm:  Scan width in mm.
            height_mm: Scan height in mm.
            step_mm:   Step size in mm (should match camera FOV width for full coverage).
            start_x:   Starting X position in mm.
            start_y:   Starting Y position in mm.

        Yields:
            (x_mm, y_mm) tuples for each scan position.
        """
        import math
        cols = math.ceil(width_mm / step_mm) + 1
        rows = math.ceil(height_mm / step_mm) + 1
        total = cols * rows
        n = 0
        for row in range(rows):
            y = start_y + row * step_mm
            col_range = range(cols) if row % 2 == 0 else range(cols - 1, -1, -1)
            for col in col_range:
                x = start_x + col * step_mm
                n += 1
                print(f"[scan] {n}/{total}  X={x:.2f}mm  Y={y:.2f}mm", end='\r')
                yield x, y
        print()  # newline after \r progress

    # ------------------------------------------------------------------
    # Power management
    # ------------------------------------------------------------------

    def disable(self):
        """De-energize stepper drivers (motors will lose holding torque)."""
        if not self.simulate:
            GPIO.output(self._pins['x_en'], GPIO.HIGH)
            GPIO.output(self._pins['y_en'], GPIO.HIGH)

    def cleanup(self):
        """Disable drivers and release GPIO."""
        self.disable()
        if not self.simulate:
            GPIO.cleanup()
        print("[stage] GPIO released.")


# ------------------------------------------------------------------
# Quick manual test
# ------------------------------------------------------------------

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Stage manual control test')
    parser.add_argument('--sim', action='store_true', help='Simulation mode (no GPIO)')
    parser.add_argument('--home', action='store_true', help='Home both axes on startup')
    parser.add_argument('--x', type=float, default=5.0, help='Move to X mm (default 5)')
    parser.add_argument('--y', type=float, default=5.0, help='Move to Y mm (default 5)')
    args = parser.parse_args()

    stage = Stage(simulate=args.sim)
    try:
        if args.home:
            stage.home()
        print(f"[stage] Moving to X={args.x} Y={args.y}")
        stage.move_to(args.x, args.y)
        print(f"[stage] Position: X={stage.x:.3f}mm  Y={stage.y:.3f}mm")
        stage.move_to(0, 0)
        print("[stage] Returned to origin.")
    finally:
        stage.cleanup()
