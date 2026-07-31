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

SRC_DIR = "/home/pi/src/"
USB_PATH = SRC_DIR + "CybikoStuff/tools/build/usbcon"
TUI_PATH = SRC_DIR + "CybikoTUI/CybikoTUI.boot"


class Pybiko:
    def __init__(self):
        try:
            # Compile the Cybiko application

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
            terminal = subprocess.Popen(
                ["/bin/sh"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # merge stderr into stdout, simpler to pipe
                text=True,
                bufsize=0,
            )

            out_q = queue.Queue()

            def reader():
                while True:
                    chunk = terminal.stdout.read(1)
                    if chunk == "":
                        break  # EOF, process exited
                    out_q.put(chunk)

            t = threading.Thread(target=reader, daemon=True)
            t.start()

            self.pserial.clear()
            self.pserial.set_cursor(0, 0)
            self.pserial.write_text("$")

            while terminal.poll() is None:
                key = self.pserial.poll_key()
                if key:
                    code, down = key
                    print(f"key {code:#x} {'down' if down else 'up'}")
                    if down:
                        try:
                            ch = code.to_bytes(1, byteorder="big", signed=False).decode("utf-8")
                            if "\b" <= ch <= "~":
                                terminal.stdin.write(ch)
                                terminal.stdin.flush()

                                # echo back
                                self.pserial.write_text(ch)
                        except UnicodeError:
                            pass

                # drain whatever output has accumulated, non-blocking
                out = []
                try:
                    while True:
                        out.append(out_q.get_nowait())
                except queue.Empty:
                    pass
                if out:
                    self.pserial.write_text("".join(out))

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
