import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_box(ax, x, y, width, height, text, color='lightblue', fontsize=10):
    # Draw rectangle
    rect = patches.Rectangle((x, y), width, height, linewidth=1.5, edgecolor='black', facecolor=color)
    ax.add_patch(rect)
    # Add text
    ax.text(x + width/2, y + height/2, text, ha='center', va='center', fontsize=fontsize, fontweight='bold')

def draw_arrow(ax, x1, y1, x2, y2, label=None, double=False):
    # Draw arrow
    style = '<->' if double else '->'
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, lw=1.5, color='black'))
    # Add label
    if label:
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        ax.text(mid_x, mid_y + 0.2, label, ha='center', va='bottom', fontsize=9, color='darkblue', backgroundcolor='white')

# Setup Canvas
fig, ax = plt.subplots(figsize=(12, 8))
ax.set_xlim(0, 16)
ax.set_ylim(0, 10)
ax.axis('off')

# --- 1. PERCEPTION LAYER ---
# Background Area
ax.add_patch(patches.Rectangle((0.5, 0.5), 5.5, 9, linewidth=1, edgecolor='gray', facecolor='#f0f0f0', linestyle='--'))
ax.text(3.25, 9.2, "Sensing Layer (Perception)", ha='center', fontsize=12, fontweight='bold')

# Nodes
draw_box(ax, 2, 4, 2.5, 2, "Raspberry Pi\nPico W\n(Controller)", color='#98FB98')
draw_box(ax, 0.8, 7, 1.5, 1, "PIR Sensor\n(Input)", color='#FFB6C1')
draw_box(ax, 4.2, 7, 1.5, 1, "Servo Motor\n(Lock)", color='#87CEFA')
draw_box(ax, 4.2, 5, 1.5, 1, "Active Buzzer\n(Alarm)", color='#87CEFA')
draw_box(ax, 4.2, 1.5, 1.5, 1, "I2C LCD\n(Display)", color='#87CEFA')

# Connections
draw_arrow(ax, 1.55, 7, 2.5, 6, "GPIO (In)")         # PIR -> Pico
draw_arrow(ax, 3.8, 6, 4.2, 7, "PWM")               # Pico -> Servo
draw_arrow(ax, 4.5, 5.5, 4.2, 5.5, "GPIO (Out)")    # Pico -> Buzzer
draw_arrow(ax, 3.8, 4, 4.2, 2.5, "I2C")             # Pico -> LCD


# --- 2. NETWORK LAYER ---
# Background Area
ax.add_patch(patches.Rectangle((6.5, 0.5), 4, 9, linewidth=1, edgecolor='gray', facecolor='#f9f9f9', linestyle='--'))
ax.text(8.5, 9.2, "Network Layer", ha='center', fontsize=12, fontweight='bold')

# Nodes
draw_box(ax, 7.25, 4.5, 2.5, 1.5, "HiveMQ Cloud\n(MQTT Broker)", color='#FFD700')

# Connections
draw_arrow(ax, 4.5, 5, 7.25, 5, "MQTT (TLS)\nWi-Fi", double=True) # Pico <-> Cloud


# --- 3. APPLICATION LAYER ---
# Background Area
ax.add_patch(patches.Rectangle((11, 0.5), 4.5, 9, linewidth=1, edgecolor='gray', facecolor='#f0f0f0', linestyle='--'))
ax.text(13.25, 9.2, "Application Layer", ha='center', fontsize=12, fontweight='bold')

# Nodes
draw_box(ax, 12, 6, 2.5, 1.5, "Mobile App\n(Android)", color='#DDA0DD')
draw_box(ax, 12, 2.5, 2.5, 1.5, "Web Browser\n(Dashboard)", color='#DDA0DD')

# Connections
draw_arrow(ax, 9.75, 5.5, 12, 6.5, "MQTT (Pub/Sub)", double=True) # Cloud <-> Mobile
# Direct HTTP connection representation (Logical)
ax.annotate('', xy=(12, 3.25), xytext=(4.5, 4.5),
            arrowprops=dict(arrowstyle='<->', lw=1.5, color='red', linestyle='dashed', connectionstyle="arc3,rad=-0.2"))
ax.text(8.5, 2.5, "HTTP / AJAX (Local Network)", ha='center', fontsize=9, color='red', backgroundcolor='white')

# Save and Show
plt.tight_layout()
plt.savefig('architecture_diagram.png', dpi=300)
plt.show()