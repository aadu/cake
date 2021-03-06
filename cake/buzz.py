import atexit
import time
import pigpio
from random import randint

BUZZER_PIN = 4  # pin11

class BuzzerLCD(LCD):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pi = self.bus.pi
        self.pi.set_mode(BUZZER_PIN, pigpio.OUTPUT)
        self.pi.write(BUZZER_PIN, pigpio.HIGH)
        atexit.register(self.destroy)

    def destroy(self):
        self.pi.write(BUZZER_PIN, pigpio.HIGH)
        self.pi.cleanup()


    def _beep(self, seconds=None):
        if seconds is None:
            seconds = randint(5, 100) / 1000
        self.pi.write(BUZZER_PIN, pigpio.LOW)
        time.sleep(seconds)
        self.pi.write(BUZZER_PIN, pigpio.HIGH)
        time.sleep(seconds)

    def write(self, value):
        self._beep()
        super().write(value)
