#!/usr/bin/env python3
"""
CybikoSerial — host-side driver matching the TLV protocol in protocol.h.

Frame format: [TYPE:1][LEN:1][PAYLOAD:LEN][CHECKSUM:1]
checksum = XOR of TYPE, LEN, and all payload bytes.
"""
import serial
import enum
from functools import reduce
from typing import Optional, Tuple


class CommandType(enum.IntEnum):
    CMD_CLEAR       = 0x01  # Pi -> Cybiko, no payload
    CMD_SET_CURSOR  = 0x02  # Pi -> Cybiko, payload: row, col
    CMD_WRITE_TEXT  = 0x03  # Pi -> Cybiko, payload: ASCII bytes
    CMD_PUT_CHAR    = 0x04  # Pi -> Cybiko, payload: row, col, char
    CMD_PING        = 0x05  # Pi -> Cybiko, no payload

    EVT_KEY         = 0x81  # Cybiko -> Pi, payload: keycode, state (1=down, 0=up)
    EVT_PONG        = 0x82  # Cybiko -> Pi, no payload


class ChecksumError(Exception):
    pass


class PybikoSerial:
    def __init__(self, port: str = "/dev/ttyS0", baud: int = 9600, timeout: float = 1.0):
        self.serial = serial.Serial(port, baud, bytesize=8, parity="N",
                                     stopbits=1, timeout=timeout)

    def close(self):
        self.serial.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @staticmethod
    def _checksum(cmd_type: int, payload: bytes) -> int:
        return reduce(lambda a, b: a ^ b, [cmd_type, len(payload), *payload], 0)

    def send_command(self, command: CommandType, data: bytes = b""):
        if len(data) > 255:
            raise ValueError("payload too long for 1-byte length field")
        checksum = self._checksum(command, data)
        frame = bytes([command, len(data)]) + data + bytes([checksum])
        self.serial.write(frame)

    def read_frame(self) -> Optional[Tuple[int, bytes]]:
        """Blocks up to `timeout` waiting for one full, checksum-valid frame.
        Returns (type, payload) or None on timeout. Raises ChecksumError on
        a bad checksum rather than silently resyncing, since on the host
        side you usually want to know a frame was corrupted."""
        header = self.serial.read(2)
        if len(header) < 2:
            return None  # timed out waiting for a frame to start
        cmd_type, length = header[0], header[1]

        payload = self.serial.read(length)
        if len(payload) < length:
            return None  # timed out mid-frame

        checksum_byte = self.serial.read(1)
        if len(checksum_byte) < 1:
            return None

        expected = self._checksum(cmd_type, payload)
        if checksum_byte[0] != expected:
            raise ChecksumError(
                f"bad checksum: got {checksum_byte[0]:#x}, expected {expected:#x}"
            )
        return cmd_type, payload

    # --- convenience wrappers for the Pi->Cybiko commands ---

    def clear(self):
        self.send_command(CommandType.CMD_CLEAR)

    def set_cursor(self, row: int, col: int):
        self.send_command(CommandType.CMD_SET_CURSOR, bytes([row, col]))

    def write_text(self, text: str):
        self.send_command(CommandType.CMD_WRITE_TEXT, text.encode("ascii"))

    def put_char(self, row: int, col: int, char: str):
        self.send_command(CommandType.CMD_PUT_CHAR, bytes([row, col, ord(char)]))

    def ping(self, wait_for_pong: bool = True) -> bool:
        self.send_command(CommandType.CMD_PING)
        if not wait_for_pong:
            return True
        frame = self.read_frame()
        return frame is not None and frame[0] == CommandType.EVT_PONG

    def poll_key(self) -> Optional[Tuple[int, bool]]:
        """Non-blocking-ish (respects `timeout`) check for a key event.
        Returns (keycode, is_down) or None if nothing arrived, and ignores
        any other frame types that show up while polling for keys."""
        frame = self.read_frame()
        if frame is None:
            return None
        cmd_type, payload = frame
        if cmd_type == CommandType.EVT_KEY and len(payload) >= 2:
            return payload[0], bool(payload[1])
        return None


if __name__ == "__main__":
    # basic smoke test
    with PybikoSerial(port="/dev/ttyUSB0", baud=9600) as cyb:
        print("pinging...")
        if cyb.ping():
            print("alive!")
        else:
            print("no response - check wiring/baud")

        cyb.clear()
        cyb.set_cursor(2, 3)
        cyb.write_text("HELLO CYBIKO - LOVE PI")

        print("listening for key events (Ctrl+C to stop)...")
        try:
            while True:
                key = cyb.poll_key()
                if key:
                    code, down = key
                    print(f"key {code:#x} {'down' if down else 'up'}")
        except KeyboardInterrupt:
            pass