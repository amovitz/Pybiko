#! /usr/bin/python3

try:
    from .PybikoIO import PybikoIO
    from .PybikoSerial import PybikoSerial
except ImportError:
    from PybikoIO import PybikoIO
    from PybikoSerial import PybikoSerial

from time import sleep
import subprocess

SRC_DIR = "/home/pi/src/"
USB_PATH = SRC_DIR + "CybikoStuff/tools/build/usbcon"
TUI_PATH = SRC_DIR + "CybikoTUI/CybikoTUI.boot"


class Pybiko:
    def test(self):
        try:
            # Compile the Cybiko application

            # Connect to the Reset IO
            PIO = PybikoIO()
            PIO.reset()

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
            pserial = PybikoSerial()
            retries = 10
            while not pserial.ping():
                print("no response - check wiring/baud")
                retries -= 1
                if retries <= 0:
                    raise IOError("Cannot connect to Cybiko")
                sleep(1)
            print("Cybiko connected!")

            pserial.clear()
            pserial.set_cursor(5, 2)
            pserial.write_text("HELLO CYBIKO - LOVE PI")
        except Exception as e:
            print(e)


if __name__ == "__main__":
    try:
        p = Pybiko()
        p.test()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("Err:", e)
    finally:
        print("Exiting...")
