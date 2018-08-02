import atexit
import itertools
import time
from collections import namedtuple
from dataclasses import dataclass

import pigpio

def msleep(milliseconds):
    time.sleep(milliseconds / 1000)


def usleep(microseconds):
    time.sleep(microseconds / 1000000)

@dataclass
class LCDConfig:
    rows: int
    cols: int
    dotsize: int


class c:
    # Commands
    LCD_CLEARDISPLAY = 0x01
    LCD_RETURNHOME = 0x02
    LCD_ENTRYMODESET = 0x04
    LCD_DISPLAYCONTROL = 0x08
    LCD_CURSORSHIFT = 0x10
    LCD_FUNCTIONSET = 0x20
    LCD_SETCGRAMADDR = 0x40
    LCD_SETDDRAMADDR = 0x80

    # Flags for display entry mode
    LCD_ENTRYRIGHT = 0x00
    LCD_ENTRYLEFT = 0x02
    LCD_ENTRYSHIFTINCREMENT = 0x01
    LCD_ENTRYSHIFTDECREMENT = 0x00

    # Flags for display on/off control
    LCD_DISPLAYON = 0x04
    LCD_DISPLAYOFF = 0x00
    LCD_CURSORON = 0x02
    LCD_CURSOROFF = 0x00
    LCD_BLINKON = 0x01
    LCD_BLINKOFF = 0x00

    # Flags for display/cursor shift
    LCD_DISPLAYMOVE = 0x08
    LCD_CURSORMOVE = 0x00

    # Flags for display/cursor shift
    LCD_DISPLAYMOVE = 0x08
    LCD_CURSORMOVE = 0x00
    LCD_MOVERIGHT = 0x04
    LCD_MOVELEFT = 0x00

    # Flags for function set
    LCD_8BITMODE = 0x10
    LCD_4BITMODE = 0x00
    LCD_2LINE = 0x08
    LCD_1LINE = 0x00
    LCD_5x10DOTS = 0x04
    LCD_5x8DOTS = 0x00

    # Flags for RS pin modes
    RS_INSTRUCTION = 0x00
    RS_DATA = 0x01


class SMBUS:

    def __init__(self, bus=1, address=0x27, host=None, port=8888):
        self.bus = bus
        self.address = address
        self.pi = pigpio.pi(host=host, port=port)
        self.handle = self.pi.i2c_open(self.bus, self.address)
        atexit.register(self.close)

    def write_byte(self, address, data):
        self.pi.i2c_write_byte(self.handle, data)

    def close(self):
        self.pi.i2c_close(self.handle)


class LCD:

    def __init__(self, bus=1, address=0x27, backlight=True, rows=2, cols=16, dotsize=8, auto_linebreaks=True, **kwargs):
        self._address = address
        self._backlight = backlight
        self.bus = SMBUS(bus, address, **kwargs)
        self.lcd = LCDConfig(rows, cols, dotsize)
        self._cursor_pos = (0, 0)
        self._content = None
        self.initialize()
        self.clear()
        # Set up auto linebreaks
        self.auto_linebreaks = auto_linebreaks
        self.recent_auto_linebreak = False
        self.text_align_mode = 'left'

    def initialize(self):
        self.send_command(0x33)  # Must initialize to 8-line mode at first
        msleep(5)
        self.send_command(0x32)  # Then initialize to 4-line mode
        msleep(5)
        self.send_command(0x28)  # 2 Lines & 5*7 dots
        msleep(5)
        self.send_command(0x0C)  # Enable display without cursor
        msleep(5)
        self.send_command(0x01)  # Clear Screen
        self.bus.write_byte(self._address, 0x08)

    def _write(self, value):
        buf = value | 0x08 if self._backlight else value & ~0x08
        self.bus.write_byte(self._address, buf)

    def send_command(self, value):
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

    def send_data(self, value):
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

    @property
    def cursor_pos(self):
        return self._cursor_pos

    @cursor_pos.setter
    def cursor_pos(self, value):
        if not hasattr(value, '__getitem__') or len(value) != 2:
            raise ValueError(
                'Cursor position should be determined by a 2-tuple.')
        row, col = value
        if row not in range(self.lcd.rows) or col not in range(self.lcd.cols):
            msg = 'Cursor position {pos!r} invalid on a {lcd.rows}x{lcd.cols} LCD.'
            raise ValueError(msg.format(pos=value, lcd=self.lcd))
        row_offsets = [0x00, 0x40, self.lcd.cols, 0x40 + self.lcd.cols]
        self._cursor_pos = value
        self.send_command(c.LCD_SETDDRAMADDR | row_offsets[row] + col)
        usleep(50)

    def backlight(self):
        self._backlight = not self._backlight
        self.send_command(0x00)
        msleep(2)

    def clear(self):
        self.send_command(0x01)  # Clear Screen
        self._cursor_pos = (0, 0)
        self._content = [[0x20] * self.lcd.cols for _ in range(self.lcd.rows)]
        msleep(2)

    def write(self, value):
        row, col = self._cursor_pos
        try:
            if self._content[row][col] != value:
                self.send_data(value)
                self._content[row][col] = value
                unchanged = False
            else:
                unchanged = True
        except IndexError as e:
            # Position out of range
            if self.auto_linebreaks is True:
                raise e
            self.send_data(value)
            unchanged = False

        # Update cursor position.
        if self.text_align_mode == 'left':
            if self.auto_linebreaks is False or col < self.lcd.cols - 1:
                # No newline, update internal pointer
                newpos = (row, col + 1)
                if unchanged:
                    self.cursor_pos = newpos
                else:
                    self._cursor_pos = newpos
                self.recent_auto_linebreak = False
            else:
                # Newline, reset pointer
                if row < self.lcd.rows - 1:
                    self.cursor_pos = (row + 1, 0)
                else:
                    self.cursor_pos = (0, 0)
                self.recent_auto_linebreak = True
        else:
            if self.auto_linebreaks is False or col > 0:
                # No newline, update internal pointer
                newpos = (row, col - 1)
                if unchanged:
                    self.cursor_pos = newpos
                else:
                    self._cursor_pos = newpos
                self.recent_auto_linebreak = False
            else:
                # Newline, reset pointer
                if row < self.lcd.rows - 1:
                    self.cursor_pos = (row + 1, self.lcd.cols - 1)
                else:
                    self.cursor_pos = (0, self.lcd.cols - 1)
                self.recent_auto_linebreak = True

    def print(self):
        lines = [''.join([chr(c) for c in row]) for row in self._content]
        print('\n'.join(lines))


def sliding_window(seq, lookahead):
    """
    Create a sliding window with the specified number of lookahead characters.
    """
    it = itertools.chain(iter(seq), ' ' * lookahead)  # Padded iterator
    window_size = lookahead + 1
    result = tuple(itertools.islice(it, window_size))
    if len(result) == window_size:
        yield result
    for elem in it:
        result = result[1:] + (elem,)
        yield result
