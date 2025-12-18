# Smart Intrusion Detection & Access Control System

**University of Oulu | 521290S Internet of Things (2025)**

## 📸 Project Overview

> **Note:** This project is a **Smart Intrusion Detection & Access Control System** developed using the **Raspberry Pi Pico W**.

It utilizes an End-to-End IoT architecture to process sensor data at the edge, detecting unauthorized access and communicating via the **MQTT protocol** to a custom **Web Application**. Unlike traditional passive alarms, this system offers real-time bidirectional control, allowing users to monitor status and remotely lock/unlock the system from anywhere via the cloud.

🔗[Live Web App Dashboard](https://fahadibnefahian.com/iot/)

## Key Features

- **Motion Detection:** Uses a PIR sensor with software-based signal debouncing to filter noise.
- **Visual & Audio Feedback:** NeoPixel LED strip indicates system state along with buzzer alerts:
  - 🟢 **Green:** Open
  - 🔵 **Blue:** Armed
  - 🔴 **Red:** Alarm
  - 🟡 **Yellow:** Warmup/Lockout
- **Remote Control:** A responsive Web App (HTML/Tailwind) connects to HiveMQ to control the device remotely.
- **Security:** Implements a lockout mechanism (3 failed PIN attempts triggers a system lockdown).
- **Asynchronous Multitasking:** Runs sensor polling, MQTT communication, and a local web server concurrently using `uasyncio`.

## 🏗️ Architecture

The system follows a 4-layer IoT architecture:
**Sensing (Edge) → Networking (MQTT) → Data Management → Application**

- **Edge:** Raspberry Pi Pico W + Sensors/Actuators.
- **Broker:** HiveMQ Cloud (SSL/TLS Encrypted).
- **UI:** Web Application (HTML/JS/Tailwind).

![Architecture Diagram](images/architecture_diagram.png)

## 🔌 Hardware Wiring

Based on the final firmware configuration (`main.py`), connect your components as follows:

| Component        | Pico W Pin | Description                |
| :--------------- | :--------- | :------------------------- |
| **PIR Sensor**   | GP7        | Digital Input (Motion)     |
| **Buzzer**       | GP5        | PWM Output (Alarm)         |
| **NeoPixel LED** | GP16       | Data Input (Visual Status) |
| **LCD SDA**      | GP2        | I2C Data                   |
| **LCD SCL**      | GP3        | I2C Clock                  |
| **VCC/GND**      | VBUS/GND   | Power rails (5V)           |

![Wiring Diagram](images/wiring.jpg)

## 🛠️ Setup & Installation

### 1. Prerequisites

- **Thonny IDE** installed on your computer.
- **MicroPython firmware** flashed onto the Raspberry Pi Pico W.
- **HiveMQ Cloud** account (for the MQTT broker).

### 2. Library Installation

Open Thonny, go to **Tools > Manage Packages**, and install the following:

- `micropython-umqtt.simple`

**Note:** You also need to manually upload the following driver files to the Pico W (found in the `lib` folder of this repo):

- `machine_i2c_lcd.py`
- `lcd_api.py`
- `ws2812.py` (Required for the NeoPixel LEDs)

### 3. Configuration

- Create a file named config.py on the Pico W and add your credentials:
- ssid = "YOUR_WIFI_SSID"
- pwd = "YOUR_WIFI_PASSWORD"
- MQTT_BROKER = "your-cluster-url.s1.eu.hivemq.cloud"
- MQTT_PORT = 8883
- MQTT_USER = "your_mqtt_username"
- MQTT_PWD = "your_mqtt_password"
