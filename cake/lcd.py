
import time
import pigpio


def msleep(milliseconds):
    time.sleep(milliseconds / 1000)


def usleep(microseconds):
    time.sleep(microseconds / 1000000)


class SMBUS:

    def __init__(self, bus=1, address=0x27, host=None, port=8888):
        self.bus = bus
        self.address = address
        self.pi = pigpio.pi(host=host, port=port)
        self.handle = self.pi.i2c_open(self.bus, self.address)

    def write_byte(self, address, data):
        self.pi.i2c_write_byte(self.handle, data)

    def close(self):
        self.pi.i2c_close(self.handle)


class LCD:

    def __init__(self, bus=1, address=0x27, backlight=True, **kwargs):
        self._address = address
        self._backlight = backlight
        self.bus = SMBUS(bus, address, **kwargs)
        self.initialize()

    def initialize(self):
        self._send_instruction(0x33)  # Must initialize to 8-line mode at first
        msleep(5)
        self._send_instruction(0x32)  # Then initialize to 4-line mode
        msleep(5)
        self._send_instruction(0x28)  # 2 Lines & 5*7 dots
        msleep(5)
        self._send_instruction(0x0C)  # Enable display without cursor
        msleep(5)
        self._send_instruction(0x01)  # Clear Screen
        self.bus.write_byte(self._address, 0x08)

    def _write(self, value):
        buf = value | 0x08 if self._backlight else value & ~0x08
        self.bus.write_byte(self._address, buf)

    def _send_instruction(self, value):
        # Send bit7-4 firstly
        buf = value & 0xF0
        self._write(buf | 0x04)  # RS = 0, RW = 0, EN = 1
        msleep(2)
        self._write(buf & 0xFB)  # Make EN = 0
        usleep(1)
        # Send bit3-0 secondly
        buf = (value & 0x0F) << 4
        self._write(buf | 0x04)  # RS = 0, RW = 0, EN = 1
        msleep(2)
        self._write(buf & 0xFB)  # Make EN = 0

    def _send_data(self, value):
        # Send bit7-4 firstly
        buf = value & 0xF0
        self._write(buf | 0x05)  # RS = 1, RW = 0, EN = 1
        msleep(2)
        self._write(buf & 0xFB)  # Make EN = 0
        usleep(1)
        # Send bit3-0 secondly
        buf = (value & 0x0F) << 4
        self._write(buf | 0x05)  # RS = 1, RW = 0, EN = 1
        msleep(2)
        self._write(buf & 0xFB)  # Make EN = 0

    def backlight(self):
        self._backlight = not self._backlight
        self._send_instruction(0x00)

    def clear(self):
        self._send_instruction(0x01)  # Clear Screen

    def write(self, x, y, txt):
        if x < 0:
            x = 0
        if x > 15:
            x = 15
        if y < 0:
            y = 0
        if y > 1:
            y = 1

        # Move cursor
        addr = 0x80 + 0x40 * y + x
        self._send_instruction(addr)
        for char in txt:
            self._send_data(ord(char))
