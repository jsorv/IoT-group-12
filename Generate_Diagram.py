import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_box(ax, x, y, width, height, text, color='lightblue', fontsize=8):
    # Draw rectangle
    rect = patches.FancyBboxPatch((x, y), width, height, linewidth=1.5, edgecolor='black', facecolor=color, boxstyle='round,pad=0.2')
    ax.add_patch(rect)
    # Add text
    ax.text(x + width/2, y + height/2, text, ha='center', va='center', fontsize=fontsize, fontweight='bold', wrap=True)

def draw_arrow(ax, x1, y1, x2, y2, label=None, double=False, color='black', style='solid'):
    # Draw arrow
    arrow_style = '<->' if double else '->'
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=arrow_style, lw=1.5, color=color, linestyle=style))
    # Add label
    if label:
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        ax.text(mid_x, mid_y + 0.35, label, ha='center', va='bottom', fontsize=7.5, color='darkblue', backgroundcolor='white')

# Setup Canvas
fig, ax = plt.subplots(figsize=(22, 12)) # Increased figure size
ax.set_xlim(0, 22)
ax.set_ylim(0, 12)
ax.axis('off')

# --- LAYER 1: SENSING Layer ---
# Background
ax.add_patch(patches.Rectangle((0.5, 0.5), 5.0, 11, linewidth=1, edgecolor='gray', facecolor='#fff0f0', linestyle='--'))
ax.text(3.0, 10.9, "1. Sensing \n Layer", ha='center', fontsize=13, fontweight='bold')

# Main Controller
draw_box(ax, 1.7, 4.5, 2.8, 2.2, "Raspberry Pi\nPico W\n(RP2040)", color='#98FB98', fontsize=8.5)

# Peripherals
draw_box(ax, 0.7, 8.0, 1.8, 1.4, "PIR Sensor\n(HC-SR501)", color='#FFB6C1', fontsize=8)
draw_box(ax, 3.5, 8.0, 1.8, 1.4, "Servo\n(SG90)", color='#87CEFA', fontsize=8)
draw_box(ax, 3.5, 5.8, 1.8, 1.4, "Buzzer", color='#87CEFA', fontsize=8)
draw_box(ax, 3.5, 2.0, 1.8, 1.4, "LCD Screen\n(16x2)", color='#87CEFA', fontsize=8)

# Wiring Connections
draw_arrow(ax, 1.5, 8.0, 2.4, 6.7, "GPIO 28")         # PIR -> Pico
draw_arrow(ax, 3.1, 6.7, 3.9, 8.0, "GPIO 15\n(PWM)")  # Pico -> Servo
draw_arrow(ax, 3.1, 5.6, 3.9, 5.8, "GPIO 16")         # Pico -> Buzzer
draw_arrow(ax, 3.1, 4.4, 3.9, 2.7, "I2C\n(GP0/1)")    # Pico -> LCD


# --- LAYER 2: NETWORKING ---
# Background
ax.add_patch(patches.Rectangle((5.8, 0.5), 4.2, 11, linewidth=1, edgecolor='gray', facecolor='#ffffe0', linestyle='--'))
ax.text(7.9, 10.9, "2. Networking Layer\n(Transport)", ha='center', fontsize=13, fontweight='bold')

# Broker
draw_box(ax, 6.5, 4.8, 3.0, 1.8, "HiveMQ Cloud\n(MQTT Broker)", color='#FFD700', fontsize=8.5)

# Connection: Pico -> Broker
draw_arrow(ax, 4.5, 5.6, 6.5, 5.7, "Wi-Fi (802.11n)\nMQTT over TLS", double=True) # Increased arrow separation
ax.text(5.5, 4.2, "Infineon\nCYW43439", ha='center', fontsize=7, color='gray') # Shifted Infineon text


# --- LAYER 3: DATA MANAGEMENT ---
# Background
ax.add_patch(patches.Rectangle((10.3, 0.5), 4.5, 11, linewidth=1, edgecolor='gray', facecolor='#e0ffff', linestyle='--'))
ax.text(12.55, 10.9, "3. Data Management\n(Processing & Storage)", ha='center', fontsize=13, fontweight='bold')

# Components
draw_box(ax, 11.0, 6.5, 3.0, 1.8, "Node-RED\n(Middleware)", color='#FF6347', fontsize=8.5)
draw_box(ax, 11.0, 2.5, 3.0, 1.8, "InfluxDB\n(Time-Series DB)", color='#4682B4', fontsize=8.5)

# Connections
draw_arrow(ax, 9.5, 5.7, 11.0, 7.4, "MQTT Subscribe\n(JSON)", double=False) # Broker -> Node-RED
draw_arrow(ax, 12.5, 6.5, 12.5, 4.3, "Write Data", double=False)             # Node-RED -> InfluxDB


# --- LAYER 4: APPLICATION ---
# Background
ax.add_patch(patches.Rectangle((15.0, 0.5), 4.5, 11, linewidth=1, edgecolor='gray', facecolor='#f0e68c', linestyle='--'))
ax.text(17.25, 10.9, "4. Application Layer\n(Interaction)", ha='center', fontsize=13, fontweight='bold')

# Components
draw_box(ax, 16.0, 6.5, 3.0, 1.8, "Mobile App\n(MIT App Inv.)", color='#DDA0DD', fontsize=8.5)
draw_box(ax, 16.0, 2.5, 3.0, 1.8, "Grafana\n(Dashboard)", color='#FFA500', fontsize=8.5)

# Connections
# Mobile App interacts directly with Broker (Auth/Control)
# Draw curved line jumping over Data Layer
ax.annotate('MQTT Pub/Sub\n(Lock/Unlock)', xy=(9.5, 5.7), xytext=(16.0, 7.4),
            arrowprops=dict(arrowstyle='<->', lw=1.5, color='purple', connectionstyle="arc3,rad=-0.3"))

# Grafana reads from InfluxDB
draw_arrow(ax, 14.0, 3.4, 16.0, 3.4, "Query Data", double=False)

# Save and Show
plt.tight_layout()
plt.savefig('architecture_diagram_v2.png', dpi=300)
plt.show()