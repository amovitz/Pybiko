#! /usr/bin/python3

try:
    from .PybikoIO import PybikoIO
    from .PybikoSerial import PybikoSerial
except ImportError:
    from PybikoIO import PybikoIO
    from PybikoSerial import PybikoSerial

from time import sleep
import subprocess
import threading
import queue
import os
import pty
import fcntl
import termios
import struct

SRC_DIR = "/home/pi/src/"
USB_PATH = SRC_DIR + "CybikoStuff/tools/build/usbcon"
TUI_PATH = SRC_DIR + "CybikoTUI/CybikoTUI.boot"

def set_winsize(fd, rows, cols):
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

class Pybiko:
    def __init__(self):
        try:
            # Compile the Cybiko application
            sleep(1)

            # Connect to the Reset IO
            self.PIO = PybikoIO()
            self.PIO.reset()

            print(USB_PATH, "-b", TUI_PATH)
            # Load an application
            result = subprocess.run(
                [
                    USB_PATH,
                    "-b",
                    TUI_PATH,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            print(result.stdout)

            # Connect to serial
            self.pserial = PybikoSerial()
            retries = 10
            while not self.pserial.ping():
                retries -= 1
                if retries <= 0:
                    raise IOError("Cannot connect to Cybiko")
                sleep(1)
            print("Cybiko connected!")

            self.pserial.clear()
            self.pserial.set_cursor(5, 2)
            self.pserial.write_text("Hello Cybiko! Love, Pi")
        except Exception as e:
            print(e)

    def loop(self):
        try:
            master_fd, slave_fd = pty.openpty()
            set_winsize(master_fd, rows=12, cols=26)

            env = os.environ.copy()
            env["TERM"] = "dumb"  # or "vt100" if you want to support cursor movement/escape codes
            env["COLUMNS"] = "26"
            env["LINES"] = "12"

            terminal = subprocess.Popen(
                ["/bin/sh", "-i"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                preexec_fn=os.setsid,  # new session, slave becomes its controlling tty
                env=env,
            )
            os.close(slave_fd)  # parent doesn't need this end anymore

            out_q = queue.Queue()

            def reader():
                while True:
                    try:
                        chunk = os.read(master_fd, 1024)
                    except OSError:
                        break  # master closed, e.g. shell exited
                    if not chunk:
                        break
                    out_q.put(chunk.decode(errors="replace"))

            t = threading.Thread(target=reader, daemon=True)
            t.start()
            self.pserial.clear()

            while terminal.poll() is None:
                key = self.pserial.poll_key()
                if key:
                    code, down = key
                    print(f"key {code:#x} {'down' if down else 'up'}")
                    if down:
                        try:
                            ch = code.to_bytes(1, byteorder="big", signed=False).decode(
                                "utf-8"
                            )
                            if "\b" <= ch <= "~":
                                os.write(master_fd, ch.encode())
                        except UnicodeError:
                            pass

                out = []
                try:
                    while True:
                        out.append(out_q.get_nowait())
                except queue.Empty:
                    pass
                if out:
                    self.pserial.write_text("".join(out))

            os.close(master_fd)

        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    try:
        pyb = Pybiko()
        pyb.loop()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("Err:", e)
    finally:
        print("Exiting...")
