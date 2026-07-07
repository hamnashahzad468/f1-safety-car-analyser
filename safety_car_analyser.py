import fastf1
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import numpy as np
import os

# Setup cache
os.makedirs('f1_cache', exist_ok=True)
fastf1.Cache.enable_cache('f1_cache')

# Load 2026 Monaco GP - famous for safety cars!
session = fastf1.get_session(2026, 'Monaco', 'R')
session.load()

# Get track status data (safety car periods)
track_status = session.track_status.copy()

# Define status codes
status_map = {
    '1': 'Green',
    '2': 'Yellow',
    '4': 'Safety Car',
    '5': 'Red Flag',
    '6': 'Virtual Safety Car',
    '7': 'VSC Ending'
}

track_status['StatusName'] = track_status['Status'].map(status_map).fillna('Unknown')

# Get top 5 drivers lap data
drivers = ['RUS', 'ANT', 'LEC', 'HAM', 'VER']
driver_colors = {
    'RUS': '#00D2BE',
    'ANT': '#00A19C',
    'LEC': '#DC0000',
    'HAM': '#B0B0B0',
    'VER': '#FF8700',
}

# Collect lap data
driver_laps = {}
for driver in drivers:
    try:
        laps = session.laps.pick_drivers(driver).copy()
        laps['LapTimeSec'] = laps['LapTime'].dt.total_seconds()
        driver_laps[driver] = laps
    except:
        continue

total_laps = session.total_laps

# Convert track status time to lap number approximation
session_duration = track_status['Time'].dt.total_seconds().max()
track_status['LapApprox'] = (
    track_status['Time'].dt.total_seconds() / session_duration * total_laps)

# Identify SC and VSC periods
sc_periods = track_status[track_status['Status'] == '4']
vsc_periods = track_status[track_status['Status'] == '6']

# --- Plotting ---
fig, axes = plt.subplots(3, 1, figsize=(14, 13))
fig.suptitle('Safety Car Impact Analyser — Monaco GP 2026',
             fontsize=14, fontweight='bold')

# --- Plot 1: Lap times with SC periods shaded ---
ax1 = axes[0]

for driver, laps in driver_laps.items():
    clean = laps[laps['LapTimeSec'] < laps['LapTimeSec'].median() * 1.3]
    ax1.plot(clean['LapNumber'], clean['LapTimeSec'],
             color=driver_colors[driver], linewidth=1.5,
             label=driver, alpha=0.85)

# Shade SC periods
sc_start = None
for _, row in track_status.iterrows():
    if row['Status'] == '4' and sc_start is None:
        sc_start = row['LapApprox']
    elif row['Status'] != '4' and sc_start is not None:
        ax1.axvspan(sc_start, row['LapApprox'],
                    alpha=0.2, color='yellow', label='_SC')
        sc_start = None

# Shade VSC periods
vsc_start = None
for _, row in track_status.iterrows():
    if row['Status'] == '6' and vsc_start is None:
        vsc_start = row['LapApprox']
    elif row['Status'] != '6' and vsc_start is not None:
        ax1.axvspan(vsc_start, row['LapApprox'],
                    alpha=0.2, color='orange', label='_VSC')
        vsc_start = None

ax1.set_ylabel('Lap Time (seconds)', fontsize=10)
ax1.set_title('Driver Lap Times with Safety Car Periods', fontsize=11)
ax1.grid(True, alpha=0.3)
ax1.set_xlim(1, total_laps)

# Legend
driver_patches = [mpatches.Patch(color=driver_colors[d], label=d)
                  for d in driver_laps.keys()]
sc_patch = mpatches.Patch(color='yellow', alpha=0.4, label='Safety Car')
vsc_patch = mpatches.Patch(color='orange', alpha=0.4, label='Virtual SC')
ax1.legend(handles=driver_patches + [sc_patch, vsc_patch],
           loc='upper right', fontsize=9)

# --- Plot 2: Track status timeline ---
ax2 = axes[1]
status_colors = {
    'Green': '#00AA44',
    'Yellow': '#FFF200',
    'Safety Car': '#FF8700',
    'Virtual Safety Car': '#FF4500',
    'VSC Ending': '#FF8C00',
    'Red Flag': '#FF0000',
    'Unknown': '#888888'
}

prev_lap = 0
prev_status = None
for _, row in track_status.iterrows():
    curr_lap = row['LapApprox']
    status = row['StatusName']
    if prev_status is not None:
        color = status_colors.get(prev_status, '#888888')
        ax2.barh(0, curr_lap - prev_lap, left=prev_lap,
                 color=color, height=0.5, edgecolor='none')
    prev_lap = curr_lap
    prev_status = status

ax2.set_xlim(1, total_laps)
ax2.set_yticks([])
ax2.set_xlabel('Lap Number', fontsize=10)
ax2.set_title('Track Status Timeline', fontsize=11)

status_legend = [mpatches.Patch(color=c, label=s)
                 for s, c in status_colors.items()
                 if s not in ['Unknown', 'VSC Ending']]
ax2.legend(handles=status_legend, loc='upper right',
           fontsize=8, ncol=3)

# --- Plot 3: Average lap time per driver under each condition ---
ax3 = axes[2]

# Classify each lap as SC, VSC or Green
def get_lap_status(lap_num, track_status, total_laps):
    lap_time_frac = lap_num / total_laps
    session_time = lap_time_frac * track_status['Time'].dt.total_seconds().max()
    nearby = track_status[
        track_status['Time'].dt.total_seconds() <= session_time]
    if nearby.empty:
        return 'Green'
    return nearby.iloc[-1]['StatusName']

conditions = ['Green', 'Safety Car', 'Virtual Safety Car']
condition_colors = ['#00AA44', '#FF8700', '#FF4500']

x = np.arange(len(driver_laps))
width = 0.25

for ci, (condition, color) in enumerate(zip(conditions, condition_colors)):
    avg_times = []
    for driver, laps in driver_laps.items():
        laps_copy = laps.copy()
        laps_copy['Status'] = laps_copy['LapNumber'].apply(
            lambda n: get_lap_status(n, track_status, total_laps))
        condition_laps = laps_copy[
            (laps_copy['Status'] == condition) &
            (laps_copy['LapTimeSec'] < laps_copy['LapTimeSec'].median() * 1.5)]
        if len(condition_laps) > 0:
            avg_times.append(condition_laps['LapTimeSec'].mean())
        else:
            avg_times.append(0)

    bars = ax3.bar(x + ci * width, avg_times, width,
                   label=condition, color=color,
                   edgecolor='none', alpha=0.85)

ax3.set_xticks(x + width)
ax3.set_xticklabels(list(driver_laps.keys()), fontsize=10)
ax3.set_ylabel('Average Lap Time (seconds)', fontsize=10)
ax3.set_title('Average Lap Time by Track Condition per Driver', fontsize=11)
ax3.legend(fontsize=9)
ax3.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig('safety_car_analyser.png', dpi=150, bbox_inches='tight')
plt.show()

print(f"\nMonaco GP 2026 Track Status Summary:")
print(track_status['StatusName'].value_counts())
