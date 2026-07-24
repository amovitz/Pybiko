#! /usr/bin/python3

from time import sleep

class MockIO():
    def on(self):
        print("On")
    def off(self):
        print("Off")

class PybikoIO():
    def __init__(self):
        self.RESET_PIN = 17
        try:
            import gpiozero
            self.RESET_GPIO = gpiozero.OutputDevice(self.RESET_PIN)
        except:
            self.RESET_GPIO = MockIO()

    def reset(self):
        self.RESET_GPIO.on()
        sleep(0.025)
        self.RESET_GPIO.off()


if __name__ == "__main__":
    try:
        PIO = PybikoIO()
        PIO.reset()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("Err:", e)
    finally:
        print("Exiting...")