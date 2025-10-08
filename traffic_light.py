#!/usr/bin/env python3
import dbus
import dbus.exceptions
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import sys, signal, random


# --- BLE constants ---
BLUEZ_SERVICE_NAME = 'org.bluez'
LE_ADVERTISING_MANAGER_IFACE = 'org.bluez.LEAdvertisingManager1'
ADAPTER_IFACE = 'org.bluez.Adapter1'
ADVERTISING_IFACE = 'org.bluez.LEAdvertisement1'
DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'

# BLE Advertisement object representing a traffic light
class Advertisement(dbus.service.Object):
    PATH_BASE = '/org/bluez/example/advertisement'

    def __init__(self, bus, index, id_value, status_value, time_value):
        self.path = f"{self.PATH_BASE}{index}"
        self.bus = bus
        self.ad_type = 'peripheral'
        self.local_name = 'Traffic_light'
        self.include_tx_power = True
        self.service_uuids = []

        # Optional manufacturer data (not really used, just an example)
        self.manufacturer_data = {
            dbus.UInt16(0xFFFF): dbus.Array([dbus.Byte(0x01), dbus.Byte(0x02)], signature='y')
        }

        # BLE ServiceData contains traffic light info: [id, status, time]
        self.service_data = {
            '12345678-1234-5678-1234-56789abcdef0': dbus.Array(
                [dbus.Byte(id_value), dbus.Byte(status_value), dbus.Byte(time_value)],
                signature='y'
            )
        }

        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        props = {
            'Type': self.ad_type,
            'LocalName': self.local_name,
            'IncludeTxPower': dbus.Boolean(self.include_tx_power),
            'ManufacturerData': dbus.Dictionary(self.manufacturer_data, signature='qv'),
            'ServiceData': dbus.Dictionary(self.service_data, signature='sv')
        }
        return {'org.bluez.LEAdvertisement1': props}

    def get_path(self):
        return dbus.ObjectPath(self.path)

    # Required D-Bus methods for BLE advertisement
    @dbus.service.method('org.freedesktop.DBus.Properties', in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        return self.get_properties()['org.bluez.LEAdvertisement1']

    @dbus.service.method('org.bluez.LEAdvertisement1', in_signature='', out_signature='')
    def Release(self):
        print('Advertisement Released')

# --- Helper functions ---
def find_adapter(bus):
    manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'),
                             DBUS_OM_IFACE)
    objects = manager.GetManagedObjects()
    for path, interfaces in objects.items():
        if LE_ADVERTISING_MANAGER_IFACE in interfaces:
            return path
    return None

def register_advertisement(bus, adapter_path, ad, ad_manager):
    ad_manager.RegisterAdvertisement(ad.get_path(), {},
                                     reply_handler=lambda: print("Registered advertisement"),
                                     error_handler=lambda e: print("Error:", e))

def unregister_advertisement(ad_manager, ad):
    try:
        ad_manager.UnregisterAdvertisement(ad.get_path())
        print("Unregistered advertisement")
    except Exception as e:
        print("Error unregistering:", e)

# --- Traffic light state cycle ---
index = 0
current_ad = None

current_light = 0 
time_left = 25 

# Each tuple = (status_code, duration_in_seconds)
# Example: 1=Red, 2=Yellow, 3=Green
cycle = [
    (1, 25),
    (2, 5),
    (3, 30)
]

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter_path = find_adapter(bus)
    if not adapter_path:
        print("No adapter found.")
        sys.exit(1)

    ad_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path),
                                LE_ADVERTISING_MANAGER_IFACE)

    # Update BLE advertisement once per second  
    def update_advertisement():
        global index, current_ad, current_light, time_left

        status, duration = cycle[current_light]
        fixed_id = 1  # traffic light ID (static for this device)

        service_bytes = [fixed_id, status, time_left]

        print(f"Traffic light ID={fixed_id}, Status={status}, Time left={time_left}s")

        # Stop old advertisement before creating a new one
        if current_ad:
            try:
                ad_manager.UnregisterAdvertisement(current_ad.get_path())
            except Exception as e:
                print("Error unregistering old ad:", e)
            current_ad = None
        # Create new advertisement with updated status/time
        current_ad = Advertisement(bus, index,
                                id_value=service_bytes[0],
                                status_value=service_bytes[1],
                                time_value=service_bytes[2])

        current_ad.service_data = {
            '12345678-1234-5678-1234-56789abcdef0': dbus.Array(service_bytes, signature='y')
        }
        register_advertisement(bus, adapter_path, current_ad, ad_manager)
        index += 1

        # Countdown time for current light phase
        time_left -= 1
        if time_left <= 0:
            current_light = (current_light + 1) % len(cycle)
            time_left = cycle[current_light][1]

        return True


    # Trigger the update every 1 second
    GLib.timeout_add_seconds(1, update_advertisement)
    # Graceful exit handler
    def stop(signum, frame):
        print("Stopping...")
        if current_ad:
            unregister_advertisement(ad_manager, current_ad)
        mainloop.quit()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    print("Advertising random ServiceData values every 1s...")
    update_advertisement()

    global mainloop
    mainloop = GLib.MainLoop()
    mainloop.run()

if __name__ == '__main__':
    main()