#! /usr/bin/python3

from .PybikoIO import PybikoIO
from .PybikoSerial import PybikoSerial
from time import sleep

class Pybiko():
    def test(self):
        try:
            # Compile the Cybiko application

            # Connect to the Reset IO
            PIO = PybikoIO()
            PIO.reset()

            # Load an application

            # Connect to serial
            pserial = PybikoSerial()
            while not pserial.ping():
                print("no response - check wiring/baud")
                sleep(1)

            pserial.clear()
            pserial.set_cursor(2, 3)
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