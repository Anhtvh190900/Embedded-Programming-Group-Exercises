#!/usr/bin/env python3
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import sys, signal
import random

# --- BLE constants ---
BLUEZ_SERVICE_NAME = 'org.bluez'
LE_ADVERTISING_MANAGER_IFACE = 'org.bluez.LEAdvertisingManager1'
ADAPTER_IFACE = 'org.bluez.Adapter1'
ADVERTISING_IFACE = 'org.bluez.LEAdvertisement1'
DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'

# Simple BLE Advertisement object
class Advertisement(dbus.service.Object):
    PATH_BASE = '/org/bluez/example/advertisement'

    def __init__(self, bus, index, id_value, status_value, person_type):
        self.path = f"{self.PATH_BASE}{index}"
        self.bus = bus
        self.ad_type = 'peripheral'
        self.local_name = 'Perdestrian'
        self.include_tx_power = True

        # BLE ServiceData payload (id, status, type)
        self.service_data = {
            '12345678-1234-5678-1234-56789abcdef1': dbus.Array(
                [dbus.Byte(id_value), dbus.Byte(status_value), dbus.Byte(person_type)],
                signature='y'
            )
        }
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        props = {
            'Type': self.ad_type,
            'LocalName': self.local_name,
            'IncludeTxPower': dbus.Boolean(self.include_tx_power),
            'ServiceData': dbus.Dictionary(self.service_data, signature='sv')
        }
        return {'org.bluez.LEAdvertisement1': props}

    def get_path(self):
        return dbus.ObjectPath(self.path)

    # Required D-Bus interface methods
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

def register_advertisement(bus, adapter_path, ad_manager, ad):
    ad_manager.RegisterAdvertisement(ad.get_path(), {},
                                     reply_handler=lambda: print("Advertisement registered"),
                                     error_handler=lambda e: print("Failed to register advertisement:", e))

def unregister_advertisement(ad_manager, ad):
    try:
        ad_manager.UnregisterAdvertisement(ad.get_path())   
        print("Advertisement unregistered")
    except Exception as e:
        print("Failed to unregister advertisement:", e)

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter_path = find_adapter(bus)
    if not adapter_path:
        print("No adapter found.")
        sys.exit(1)

    ad_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path),
                                LE_ADVERTISING_MANAGER_IFACE)

    ID = 2
    index = 0
    current_ad = None

    # Function to refresh BLE advertisement every second
    def update_ad():
        nonlocal index, current_ad
        status = random.randint(0, 1)                         # 0 = Waiting, 1 = Moving
        person_type = random.randint(0, 3)                    # 0=Adult, 1=Pregnant, 2=Elderly, 3=Child
 
        status_text = {0: "Waiting", 1: "Moving"}.get(status, "Unknown")
        person_type_text = {
            0: "Adult",
            1: "Pregnant Woman",
            2: "Elderly",
            3: "Child"
        }.get(person_type, "Unknown")

        print(f"Advertising ID={ID}, Status={status_text} ({status}), PersonType={person_type_text} ({person_type})")

        # Unregister the old advertisement before creating a new one
        if current_ad:
            try:
                ad_manager.UnregisterAdvertisement(current_ad.get_path())
            except Exception as e:
                print("Error unregistering old ad:", e)
            current_ad = None

        # Create and register a new advertisement with updated data
        current_ad = Advertisement(bus, index, ID, status, person_type)
        register_advertisement(bus, adapter_path, ad_manager, current_ad)
        index += 1

        return True

    # Update BLE data every second
    GLib.timeout_add_seconds(1, update_ad)
    
    # Graceful shutdown when pressing Ctrl+C
    def stop(signum, frame):
        print("\nStopping advertisement...")
        if current_ad:
            unregister_advertisement(ad_manager, current_ad)
        mainloop.quit()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    print("Starting advertising random status and person type every 1 second...")
    update_ad()

    global mainloop
    mainloop = GLib.MainLoop()
    mainloop.run()

if __name__ == '__main__':
    main()
