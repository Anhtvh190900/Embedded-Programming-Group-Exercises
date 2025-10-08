# Bluetooth & MQTT-Based V2X for Intelligent Transportation

**Course:** Advanced Embedded System  
**Assignment (Group):** Bluetooth and MQTT-Based V2X Communication in Intelligent Transportation  
**Authors:** Bùi Nguyễn Hoài Thương · Trương Vũ Hoàng Anh · Phạm Thành Toàn

## Description
This project delivers a compact V2X prototype built in Python using BlueZ/D-Bus for BLE and MQTT for upstream telemetry. Two non-connectable BLE advertisers encode domain states as 3-byte Service Data: the traffic light broadcasts [ID, STATUS, TIME_REMAIN], and the pedestrian broadcasts [ID, STATUS, TYPE]. A vehicle observer continuously scans, classifies frames by UUID, decodes the payloads, fuses them with the vehicle’s (x, y) position and timestamp, publishes to an MQTT broker, and persists positions in a MariaDB database. The implementation validates an end-to-end, connection-free pipeline aligned with V2X communication patterns for intelligent transportation demos.

