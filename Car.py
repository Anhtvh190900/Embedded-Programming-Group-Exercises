#!/usr/bin/env python3
import dbus
import dbus.mainloop.glib
from gi.repository import GLib
import signal
import sys
import paho.mqtt.client as mqtt
import json
import random
import threading
import time
import mariadb
# -------- MQTT Setup --------
broker = "broker.emqx.io"
port = 1883
topic = "test/bledata"

client = mqtt.Client()
client.connect(broker, port)

# -------- BLE Setup --------
BLUEZ_SERVICE_NAME = 'org.bluez'
ADAPTER_IFACE = 'org.bluez.Adapter1'
DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'
DBUS_PROP_IFACE = 'org.freedesktop.DBus.Properties'

TRAFFICLIGHT_UUID = "12345678-1234-5678-1234-56789abcdef0"
PEDESTRIAN_UUID  = "12345678-1234-5678-1234-56789abcdef1"

status_list = ['Waiting', 'Moving']
type_list = ['Adult', 'Pregnant Woman', 'Elderly', 'Child']

# Car ID for database & MQTT
idcar =123

# Connect to MariaDB
conn = mariadb.connect(
    user="Toan",
    password="1234",
    database="Vehicle_to_everything",
    unix_socket="/run/mysqld/mysqld.sock"
)
cursor = conn.cursor()

# Store latest random coordinates for the car
latest_coordinate = {'x': None, 'y': None}

# -------- BLE Scanning Helpers --------
def find_adapter(bus):
    manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'), DBUS_OM_IFACE)
    for path, ifaces in manager.GetManagedObjects().items():
        if ADAPTER_IFACE in ifaces:
            return path
    return None

def decode_trafficlight(data):
    bytes_list = [int(b) for b in data]
    if len(bytes_list) != 3:
        return None
    return {'id': bytes_list[0], 'status': bytes_list[1], 'time': bytes_list[2]}

def decode_pedestrian(data):
    bytes_list = [int(b) for b in data]
    if len(bytes_list) != 3:
        return None
    ID, status_val, type_val = bytes_list
    return {
        'id': ID,
        'status': status_list[status_val] if status_val < len(status_list) else f'unknown({status_val})',
        'type': type_list[type_val] if type_val < len(type_list) else f'unknown({type_val})'
    }


# Callback for BLE property changes (new data detected)
def property_changed(interface, changed, invalidated, path):
    if interface != "org.bluez.Device1":
        return

    bus = dbus.SystemBus()
    device = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, path), DBUS_PROP_IFACE)

    try:
        name = device.Get("org.bluez.Device1", "Name")
        alias = device.Get("org.bluez.Device1", "Alias")
        addr = device.Get("org.bluez.Device1", "Address")
        service_data = device.Get("org.bluez.Device1", "ServiceData")

        # Parse traffic light broadcast data
        if TRAFFICLIGHT_UUID in service_data:
            parsed = decode_trafficlight(service_data[TRAFFICLIGHT_UUID])
            if parsed:
                log = f"[TrafficLight] Device {addr}, Name={name}, Alias={alias}\n" \
                      f"   id: {parsed['id']}, status: {parsed['status']}, time: {parsed['time']}"
                print(log)

        # Parse pedestrian broadcast data
        if PEDESTRIAN_UUID in service_data:
            parsed = decode_pedestrian(service_data[PEDESTRIAN_UUID])
            if parsed:
                log = f"[Pedestrian] Device {addr}, Name={name}, Alias={alias}\n" \
                      f"   id: {parsed['id']}, status: {parsed['status']}, type: {parsed['type']}"
                print(log)

        # Ignore read errors quietly
        print("-"*40)

    except Exception as e:
        # Uncomment để debug lỗi
        # print("Error reading device properties:", e)
        # Ignore read errors quietly
        pass

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter_path = find_adapter(bus)
    if not adapter_path:
        print("No adapter found")
        sys.exit(1)

    adapter = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path), ADAPTER_IFACE)
    adapter.SetDiscoveryFilter({"DuplicateData": dbus.Boolean(True)})
    adapter.StartDiscovery()

    # Listen for BLE property changes
    bus.add_signal_receiver(
        property_changed,
        bus_name=BLUEZ_SERVICE_NAME,
        signal_name="PropertiesChanged",
        path_keyword="path"
    )

    # Send car position every few seconds via MQTT + store in DB
    def send_position_through_mqtt():
        import json
        latest_coordinate['x'] = round(random.uniform(-100, 100), 2)
        latest_coordinate['y'] = round(random.uniform(-100, 100), 2)
        payload = json.dumps({"x": latest_coordinate['x'], "y":latest_coordinate['y']}) 
        client.publish(topic, payload)
        print(f"[Position] Id={idcar} x={latest_coordinate['x']}, y={latest_coordinate['y']}")
        sql = f"INSERT INTO Position_GPS_CAR (ID_xe, latitude, longitude) VALUES ({idcar}, {latest_coordinate['x']}, {latest_coordinate['y']});"
        cursor.execute(sql)
        conn.commit()
        return True

    # Trigger position sending every 3 seconds
    GLib.timeout_add_seconds(3, send_position_through_mqtt)

    # Keep the program running, handle Ctrl+C to stop
    loop = GLib.MainLoop()
    signal.signal(signal.SIGINT, lambda *a: loop.quit())
    print("Scanning BLE devices and publishing data to MQTT. Press Ctrl+C to stop.")
    loop.run()

    client.disconnect()

if __name__ == "__main__":
    main()
