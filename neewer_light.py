#!/usr/bin/env python3

import simplepyble
import struct
from time import sleep

class NeewerLight:
    def __init__(self, address = None):
        #FIXME:  Filter by address if there are ever multiple Neewer lights around
        self.address = address
        self.set_light_uuid = "69400002-b5a3-f393-e0a9-e50e24dcca99"
        self.set_light_service_uuid = "69400001-b5a3-f393-e0a9-e50e24dcca99"
        self.neewer_device = None
        self.adapter = None
        self.service = None
        self.characteristic = None

    def __enter__(self):
        return self

    def scan_found_callback(self, device):
        print(f"Found {device.identifier()} [{device.address()}]")
        if self.address is not None:
            if(self.address == device.address()):
                print("Found device with requested address " + self.address)
                self.adapter.scan_stop()
                self.neewer_device = device
        else:
            if 52977 in device.manufacturer_data().keys():
                print("Found Neewer device with address: " + device.address())
                self.adapter.scan_stop()
                self.neewer_device = device

    def find_device(self):
        adapters = simplepyble.Adapter.get_adapters()
        self.adapter = adapters[0]

        self.adapter.set_callback_on_scan_start(lambda: print("Scan started."))
        self.adapter.set_callback_on_scan_stop(lambda: print("Scan complete."))
        self.adapter.set_callback_on_scan_found(lambda device: self.scan_found_callback(device))

        self.adapter.scan_start()
        #FIXME:  Implement a timeout here.
        while(self.adapter.scan_is_active()):
            sleep(0.1)


    def get_characteristic(self):
        #FIXME:  Implement error handling for when the light is not found
        self.neewer_device.connect()
        services = self.neewer_device.services()

        for service in services:
            if(service.uuid() == self.set_light_service_uuid):
                print("Found expected service for setting the light")
                self.service = service
        
        for characteristic in self.service.characteristics():
            if(characteristic.uuid() == self.set_light_uuid):
                print("Found expected characteristic within service")
                self.characteristic = characteristic

    def __exit__(self, type, value, traceback):
        if self.neewer_device is not None:
            if self.neewer_device.is_connected():
                print("Disconnecting")
                self.neewer_device.disconnect()

    def set_HSI(self, hue, sat, bright):
        if(self.neewer_device is not None):
            if(not self.neewer_device.is_connected()):
                print("Connecting")
                self.neewer_device.connect()
            print("Setting light to " + str(hue) + " " + str(sat) + " " + str(bright))
            prefix = bytes.fromhex('788604')

            cmd = prefix + struct.pack('<HBB',hue, sat, bright)
            cmd = cmd + bytes((sum(cmd) & 0xff,))

            self.neewer_device.write_request(self.set_light_service_uuid, self.set_light_uuid, cmd)

if __name__ == "__main__":
    from time import sleep

    with NeewerLight() as light:
        light.find_device()
        #light.get_characteristic()
        for h in [0, 120, 240]:
            light.set_HSI(h, 100, 10)
            sleep(1)
