ssid = "JESSICA" #"change correct Wi-Fi name here"
pwd = "1234567890" #"Add your Wi-Fi password here"
MQTT_BROKER = '5b52a741d6104c309c63d2bf1884a717.s1.eu.hivemq.cloud' # broker/server URL
MQTT_PORT= 8883
MQTT_USER = 'jssuarezc'  # access username
MQTT_PWD = 'dr34msc#m3trU3' # access pwd

# Topics
TOPIC_CONTROL = b"pico/control"  # Topic to receive commands (UNLOCK, LOCK)
TOPIC_STATUS = b"pico/status"    # Topic to send updates (ARMED, ALERT)