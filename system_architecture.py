# Create a clean and readable system architecture diagram for "Option B" using matplotlib.
# The diagram will be saved as optionB_architecture.png

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.lines import Line2D
import matplotlib.patches as mpatches

# Set up the figure with higher DPI for crisp output
plt.rcParams["figure.dpi"] = 300
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["font.size"] = 9

# Create figure with better proportions
fig, ax = plt.subplots(figsize=(16, 12))
ax.set_xlim(0, 120)
ax.set_ylim(0, 100)
ax.axis("off")

# Color scheme for better readability
colors = {
    'primary': '#2E86AB',      # Blue for main components
    'secondary': '#A23B72',    # Purple for secondary components
    'accent': '#F18F01',       # Orange for highlights
    'neutral': '#F7F7F7',      # Light gray for backgrounds
    'text': '#2C3E50',         # Dark blue-gray for text
    'border': '#BDC3C7',       # Light gray for borders
    'success': '#27AE60',      # Green for success states
    'warning': '#E67E22'       # Orange for warnings
}

def create_box(x, y, w, h, title, lines=None, color='primary', alpha=0.1):
    """Create a clean, styled box with title and content lines"""
    # Main box
    rect = FancyBboxPatch((x, y), w, h, 
                         boxstyle="round,pad=0.02,rounding_size=0.5",
                         linewidth=1.5, 
                         edgecolor=colors[color], 
                         facecolor=colors['neutral'],
                         alpha=alpha)
    ax.add_patch(rect)
    
    # Title with background
    title_bg = Rectangle((x, y + h - 2.5), w, 2.5, 
                        facecolor=colors[color], alpha=0.8)
    ax.add_patch(title_bg)
    ax.text(x + w/2, y + h - 1.25, title, 
            fontsize=10, fontweight='bold', 
            ha='center', va='center', color='white')
    
    # Content lines
    if lines:
        for i, line in enumerate(lines):
            y_pos = y + h - 4 - 1.8*i
            ax.text(x + 1, y_pos, line, 
                   fontsize=8, va='top', ha='left',
                   color=colors['text'])
    return rect

def create_arrow(xy1, xy2, label=None, arrow_type='solid', color='primary'):
    """Create a styled arrow with optional label"""
    if arrow_type == 'solid':
        arrow = FancyArrowPatch(xy1, xy2, 
                               arrowstyle="->", 
                               mutation_scale=12, 
                               lw=1.5,
                               color=colors[color])
    elif arrow_type == 'curved':
        arrow = FancyArrowPatch(xy1, xy2, 
                               arrowstyle="->", 
                               mutation_scale=12, 
                               lw=1.5,
                               connectionstyle="arc3,rad=0.2",
                               color=colors[color])
    elif arrow_type == 'dashed':
        arrow = FancyArrowPatch(xy1, xy2, 
                               arrowstyle="->", 
                               mutation_scale=12, 
                               lw=1.5,
                               linestyle='--',
                               color=colors[color])
    
    ax.add_patch(arrow)
    
    if label:
        midx = (xy1[0] + xy2[0]) / 2.0
        midy = (xy1[1] + xy2[1]) / 2.0
        # Add background for label readability
        text_bbox = dict(boxstyle="round,pad=0.3", 
                        facecolor='white', 
                        alpha=0.8,
                        edgecolor=colors['border'])
        ax.text(midx, midy + 1, label, 
               fontsize=7, ha='center', va='center',
               bbox=text_bbox,
               color=colors['text'])

# Title section
title_bg = Rectangle((0, 95), 120, 5, 
                    facecolor=colors['primary'], alpha=0.9)
ax.add_patch(title_bg)
ax.text(60, 97.5, "Option B — Native Unity Picker", 
        fontsize=16, ha='center', fontweight='bold', color='white')
ax.text(60, 96, "System Architecture Overview", 
        fontsize=12, ha='center', color='white')

# Network Infrastructure (top section)
create_box(50, 85, 20, 8, "Wi-Fi 6/6E Access Point", [
    "SSID: rehab-lab-5G/6G",
    "Security: WPA2/3",
    "DHCP: Static reservations",
    "L2 Isolation: Disabled"
], 'primary')

# Edge Hub (central component)
create_box(35, 60, 50, 20, "Edge Hub (Raspberry Pi 4 / Mini-PC)", [
    "• Mosquitto MQTT Broker (1883/8883)",
    "• IMU Data Ingestion (UDP/TCP)",
    "• Sensor Fusion & AHRS Processing",
    "• Kinematics & Joint Angle Calculation",
    "• Session Management & Orchestration",
    "• Haptic Device Controller",
    "• Data Logging (CSV/Parquet/DB)",
    "• Streamlit Clinician Interface",
    "• NTP Time Synchronization Server"
], 'primary', 0.15)

# Clinician UI
create_box(5, 75, 25, 15, "Clinician UI (Streamlit)", [
    "Web Interface: Oculus/Desktop Browser",
    "Exercise Selection & Configuration",
    "Real-time Monitoring & Controls",
    "Session Start/Stop Commands",
    "Live Data Visualization",
    "Calibration Interface",
    "Session Notes & Documentation"
], 'secondary')

# Meta Quest 3
create_box(90, 60, 25, 20, "Meta Quest 3 (Unity/OpenXR)", [
    "• Exercise Selection Scene (XR UI)",
    "• Immersive Game Scenes (Addressables)",
    "• MQTT Client Integration",
    "• Topics: angles/*, session/*, haptics/*",
    "• Publications: game/events, haptics/ack",
    "• Passthrough & XR Hand Tracking",
    "• Real-time Pose & Gesture Recognition"
], 'accent', 0.15)

# IMU Sensors (left side)
imu_positions = [
    (5, 45), (32, 45),   # Top row
    (5, 35), (32, 35),   # Middle row  
    (5, 25), (32, 25)    # Bottom row
]
imu_titles = ["Wrist R", "Wrist L", "Upper Arm R", "Upper Arm L", "Scapula/Trunk R", "Scapula/Trunk L"]
imu_boxes = []

for i, (x, y) in enumerate(imu_positions):
    box = create_box(x, y, 25, 8, f"IMU: {imu_titles[i]}", [
        "x-IMU3 Sensor over Wi-Fi",
        "UDP/TCP Quaternions @100-200Hz",
        "Clock sync: Device or Hub-based"
    ], 'secondary')
    imu_boxes.append(box)

# ESP32 Haptic Devices (right side)
haptic_positions = [
    (95, 35), (108, 35),  # Top row
    (95, 25), (108, 25),  # Middle row
    (95, 15), (108, 15)   # Bottom row
]
haptic_titles = ["Deltoid R", "Deltoid L", "Forearm R", "Forearm L", "Scapula R", "Scapula L"]
haptic_boxes = []

for i, (x, y) in enumerate(haptic_positions):
    box = create_box(x, y, 12, 6, f"Haptic: {haptic_titles[i]}", [
        "ESP32 + ERM/LRA Driver",
        "MQTT Sub: haptics/<location>",
        "3s vibration → acknowledgment"
    ], 'warning', 0.15)
    haptic_boxes.append(box)

# Data Store (bottom)
create_box(35, 10, 50, 12, "Enterprise Data Store (Optional)", [
    "Database: TimescaleDB/PostgreSQL",
    "Session Logs & Performance Metrics",
    "Analytics & Reporting Engine",
    "Backup & Retention Policies",
    "PHI-compliant Data Security",
    "Integration with Clinical Systems"
], 'success', 0.1)

# Legend (bottom left)
legend_items = [
    "Solid Arrow: Direct TCP/UDP Connection",
    "Curved Arrow: MQTT Pub/Sub Communication", 
    "Dashed Arrow: Time Synchronization",
    "Colors: Component Type Classification",
    "Security: WPA2/3, TLS (8883), Authentication"
]

legend_bg = Rectangle((5, 10), 25, 12, 
                     facecolor=colors['neutral'], alpha=0.8,
                     edgecolor=colors['border'], linewidth=1)
ax.add_patch(legend_bg)

ax.text(17.5, 21, "Protocol Legend", 
        fontsize=11, ha='center', fontweight='bold', 
        color=colors['text'])

for i, item in enumerate(legend_items):
    ax.text(7, 19 - 1.5*i, "• " + item, 
           fontsize=8, ha='left', 
           color=colors['text'])

# Connection arrows with improved styling
# Wi-Fi connections
create_arrow((60, 85), (17.5, 82.5), "Wi-Fi 6/6E", 'solid', 'primary')  # AP to Clinician UI
create_arrow((70, 85), (102.5, 70), "Wi-Fi 6/6E", 'solid', 'primary')   # AP to Quest 3
create_arrow((70, 85), (60, 80), "LAN", 'solid', 'primary')             # AP to Hub

# MQTT communications (curved)
create_arrow((85, 65), (102.5, 65), "angles/*, session/*", 'curved', 'secondary')
create_arrow((102.5, 60), (85, 60), "game/events, haptics/ack", 'curved', 'secondary')

# IMU data flows
for i, imu in enumerate(imu_boxes):
    create_arrow((imu.get_x() + 25, imu.get_y() + 4), (35, 70 - i*2), "UDP/TCP", 'solid', 'secondary')

# Haptic control flows
for i, haptic in enumerate(haptic_boxes):
    create_arrow((85, 50 - i*2), (haptic.get_x(), haptic.get_y() + 3), "haptics/<loc>", 'curved', 'warning')

# Time sync (dashed)
for i, imu in enumerate(imu_boxes):
    create_arrow((imu.get_x() + 12.5, imu.get_y() + 8), (60, 67), "", 'dashed', 'accent')

for i, haptic in enumerate(haptic_boxes):
    create_arrow((haptic.get_x() + 6, haptic.get_y() + 6), (60, 67), "", 'dashed', 'accent')

ax.text(62, 67.5, "NTP Time Sync", fontsize=8, 
        bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8),
        color=colors['text'])

# Clinician UI to Hub
create_arrow((30, 82.5), (85, 75), "session/selected_game", 'curved', 'secondary')

# Security notes
security_bg = Rectangle((35, 45), 50, 3, 
                       facecolor=colors['success'], alpha=0.2,
                       edgecolor=colors['success'], linewidth=0.5)
ax.add_patch(security_bg)

ax.text(60, 46.5, "Security Features: TLS Encryption (MQTT 8883) • Authentication (username/password) • DHCP Reservations • Static IP Configuration • PHI-Safe Data Policies", 
       fontsize=8, ha='center', va='center',
       bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.9),
       color=colors['text'])

# Save with high quality
out_path = "optionB_architecture.png"
plt.tight_layout(pad=0.5)
plt.savefig(out_path, bbox_inches="tight", dpi=300, 
            facecolor='white', edgecolor='none',
            pad_inches=0.1)

print(f"Architecture diagram saved as: {out_path}")
print("Diagram features:")
print("- High resolution (300 DPI)")
print("- Clean typography and spacing")
print("- Color-coded components")
print("- Professional layout and styling")
print("- Improved readability and organization")
