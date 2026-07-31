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
from time import sleep, time


class CommandType(enum.IntEnum):
    # N/ACK
    EVT_ACK         = 0x00  # Bi-Drirectional, no payload
    EVT_NACK        = 0xFF  # Bi-Drirectional, no payload

    # Ping/Pong
    CMD_PING        = 0xC0  # Pi -> Cybiko, no payload
    EVT_PONG        = 0xE0  # Cybiko -> Pi, no payload

    # Screen commands
    CMD_CLEAR       = 0xC1  # Pi -> Cybiko, no payload
    CMD_SET_CURSOR  = 0xC2  # Pi -> Cybiko, payload: row, col
    CMD_WRITE_TEXT  = 0xC3  # Pi -> Cybiko, payload: ASCII bytes
    CMD_PUT_CHAR    = 0xC4  # Pi -> Cybiko, payload: row, col, char

    # Keyboard
    CMD_DUMP_KEYS   = 0xC6  # Pi -> Cybiko, no payload -- request a raw keyboard scan
    EVT_KEY         = 0xE1  # Cybiko -> Pi, payload: keycode, state (1=down,0=up)
    EVT_DEBUG       = 0xDB  # Cybiko -> Pi, payload: 10x uint16 LE (low byte=rows0-7, high byte=rows8-15), one pair per column in scan order


FRAME_SYNC = 0xAA

class ChecksumError(Exception):
    pass


class PybikoSerial:
    def __init__(self, port: str = "/dev/ttyS0", baud: int = 115200, timeout: float = 0.5):
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
        self.serial.write(bytes([FRAME_SYNC]))
        self.serial.write(frame)
        print('>', hex(command), hex(len(data)), data.hex(), hex(checksum))


    def read_frame(self) -> Optional[Tuple[int, bytes]]:
        """Blocks up to `timeout` waiting for one full, checksum-valid frame.
        Returns (type, payload) or None on timeout. Raises ChecksumError on
        a bad checksum rather than silently resyncing, since on the host
        side you usually want to know a frame was corrupted."""
        sync = self.serial.read(1)
        if len(sync) < 1 or sync[0] != FRAME_SYNC:
            return None # out of sync
        header = self.serial.read(2)
        if len(header) < 2:
            return None  # timed out waiting for a frame to start
        cmd_type, length = header[0], header[1]
        print('<', hex(cmd_type), hex(length), end=' ')

        payload = self.serial.read(length)
        print(payload.hex(), end=' ')
        if len(payload) < length:
            return None  # timed out mid-frame

        checksum_byte = self.serial.read(1)
        print(hex(checksum_byte[0]))
        if len(checksum_byte) < 1:
            return None

        expected = self._checksum(cmd_type, payload)
        if checksum_byte[0] != expected:
            print (
                f"bad checksum: got {checksum_byte[0]:#x}, expected {expected:#x}"
            )
            return None
        return cmd_type, payload

    def wait_for_response(self, command: CommandType = CommandType.EVT_ACK, timeout: float = 0.5):
        START = time()
        while time() < START + timeout:
            frame = self.read_frame()
            if frame is not None and frame[0] == command:
                return True
        return False

    # --- convenience wrappers for the Pi->Cybiko commands ---

    def clear(self, wait_for_ack: bool = True):
        self.send_command(CommandType.CMD_CLEAR)
        if not wait_for_ack:
            return True
        return self.wait_for_response()

    def set_cursor(self, row: int, col: int, wait_for_ack: bool = True):
        self.send_command(CommandType.CMD_SET_CURSOR, bytes([row, col]))
        if not wait_for_ack:
            return True
        return self.wait_for_response()

    def write_text(self, text: str, wait_for_ack: bool = True):
        self.send_command(CommandType.CMD_WRITE_TEXT, text.encode("ascii"))
        if not wait_for_ack:
            return True
        return self.wait_for_response()

    def put_char(self, row: int, col: int, char: str, wait_for_ack: bool = True):
        self.send_command(CommandType.CMD_PUT_CHAR, bytes([row, col, ord(char)]))
        if not wait_for_ack:
            return True
        return self.wait_for_response()

    def ping(self, wait_for_pong: bool = True) -> bool:
        self.send_command(CommandType.CMD_PING)
        if not wait_for_pong:
            return True
        return self.wait_for_response(CommandType.EVT_PONG)

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
    with PybikoSerial() as cyb:
        retries = 10
        print("pinging...")
        if cyb.ping():
            print("alive!")
        else:
            print("no response - check wiring/baud")
            retries -= 1
            if retries <= 0:
                raise IOError("Failed to connect to Cybiko")

        cyb.clear()
        cyb.set_cursor(5, 2)
        cyb.write_text("Hello Cybiko! Love, Pi")

        print("listening for key events (Ctrl+C to stop)...")
        try:
            while True:
                key = cyb.poll_key()
                if key:
                    code, down = key
                    print(f"key {code:#x} {'down' if down else 'up'}")
        except KeyboardInterrupt:
            pass