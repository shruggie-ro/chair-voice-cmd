#!/usr/bin/python

# Library for PiRelay V2
# Developed by: SB Components
# Author: Satyam
# Project: PiRelay-V2
# Python: 3.7.3


import logging
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

FORMAT = '%(asctime)-15s %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
logger = logging.getLogger(__name__)

class Relay:
    ''' Class to handle Relay

    Arguments:
    relay = string Relay label (i.e. "RELAY1","RELAY2","RELAY3","RELAY4")
    '''
    relaypins = {"RELAY1":35, "RELAY2":33, "RELAY3":31, "RELAY4":29}


    def __init__(self, relay):
        self.pin = self.relaypins[relay]
        self.relay = relay
        GPIO.setup(self.pin,GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)

    def on(self):
        logger.debug(self.relay + " - ON")
        GPIO.output(self.pin,GPIO.HIGH)

    def off(self):
        logger.debug(self.relay + " - OFF")
        GPIO.output(self.pin,GPIO.LOW)

