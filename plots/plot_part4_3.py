import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
from collections import defaultdict
from datetime import datetime, timezone

JOB_COLORS = {
    "blackscholes": "#CCA000",
    "canneal": "#CCCCAA",
    "dedup": "#CCACCA",  
    "ferret": "#AACCCA", 
    "freqmine": "#0CCA00",
    "radix": "#00CCA0",  
    "vips": "#CC0A00",
    "memcached" : "#888888"   
}
jobs = ['blackscholes', 'canneal', 'dedup', 'ferret', 'freqmine', 'radix', 'vips']


actions = defaultdict(lambda: list())



timestamps = None
interval_offsets = None
ts_start = None
qps = []
p95 = []

with open("../part4/results/subpart2/results-part4.2-13-05-2025-18-51.txt", "r") as f:
    lines = f.readlines()
    intervals_line = lines[1].split()
    num_intervals = int(intervals_line[5])
    
    intervals = intervals_line[6:]
    intervals[0] = intervals[0][1:]
    intervals[-1] = intervals[-1][:-1]
    intervals = [int(i[:-1]) for i in intervals]
    interval_offsets = [0] + [sum(intervals[:i]) / 10000 for i in range(1, num_intervals + 1)]

    ts_start = int(lines[3].split()[-1])
    ts_end = int(lines[4].split()[-1])
    timestamps = [ts_start + offset for offset in interval_offsets]

    for line in lines:
         print(line)
         split = line.split()
         if split and split[0] == "read":
              p95.append(float(split[12]) / 1000)
              qps.append(float(split[16]))


with open("../part4/results/subpart2/container-runtime-13-05-2025-18-51.txt", "r") as f:
        lines = f.readlines()
        dt = datetime.fromisoformat((lines[0].split())[0]) 
        dt = dt.replace(tzinfo=timezone.utc)
        start_time_reference =  ts_start / 1000 # dt.timestamp()

        for line in lines[1:]:
            lines_split = line.split()

            timestamp = lines_split[0]

            dt = datetime.fromisoformat(timestamp)
            dt = dt.replace(tzinfo=timezone.utc)
            started_at_ts = dt.timestamp()

            if lines_split[1] == "cpu": continue

            if lines_split[1] == "start":
                 actions[lines_split[2]].append((started_at_ts-start_time_reference, int(lines_split[-1])))
                
            if lines_split[1] == "end":
                 actions[lines_split[2]].append((started_at_ts-start_time_reference, -1))
            
            if lines_split[1] == "update_cores":
                 actions[lines_split[2]].append((started_at_ts-start_time_reference, len(lines_split[-1].split(","))))

for job in jobs:
     for action in actions[job]:
          print(action)


time = np.arange(0, 900, 10)  # every 20 seconds


# Create figure and axis
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True,
                               gridspec_kw={'height_ratios': [2, 1]})

# --- Top Plot ---
# Bar plot for QPS (right y-axis)
ax1b = ax1.twinx()
ax1b.bar(time, qps, width=10, color='royalblue', alpha=0.8, label="QPS", zorder=1)
ax1b.set_ylabel("Queries per second (QPS)", color='blue')
ax1b.tick_params(axis='y', labelcolor='blue')
ax1b.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x / 1000)}k'))

# Line plot for latency (left y-axis)
ax1.set_ylim(0, 1.2)
ax1.plot(time, p95, marker='o', color='red', label='95th Percentile Latency', zorder=2)
ax1.set_ylabel("95th percentile latency [ms]", color='coral')
ax1.tick_params(axis='y', labelcolor='coral')

# SLO line
ax1.axhline(0.8, linestyle=':', color='black', linewidth=1.5, zorder=3)
ax1.text(time[0], 1.02, "SLO (0.8 ms)", fontsize=12, va='bottom', ha='left', bbox=dict(facecolor='white', edgecolor='black'))

ax1.set_zorder(ax1b.get_zorder() + 1)
ax1.patch.set_visible(False)

# --- Bottom Plot ---
np.random.seed(0)

for i, job in enumerate(jobs):
    prev_time = actions[job][0][0]
    no_cores = actions[job][0][1]

    for action in actions[job][1:]:
        if no_cores == 2:
             bar_height = 0.5
        else:
             bar_height = 1

        y_start = i - bar_height / 2
        y_center = i
        y_range = (y_center - bar_height / 2, bar_height)

        new_time = action[0]
        ax2.broken_barh([(prev_time, new_time-prev_time)], y_range,facecolors=JOB_COLORS[job])
        prev_time = new_time
        
        no_cores = action[-1]

memcached_cores = [2]
memcached_times = [0]
prev_time = actions["memcached"][0][0]
no_cores = actions["memcached"][0][1]

for action in actions["memcached"][1:]:
    memcached_cores.append(no_cores)
    memcached_times.append(prev_time)

    new_time = action[0]
    prev_time = new_time

    # memcached_cores.append(no_cores)
    # memcached_times.append(new_time)
    
    no_cores = action[-1]

memcached_cores.append(no_cores)
memcached_times.append(900)



ax2.set_yticks(range(len(jobs)))
ax2.set_yticklabels(jobs)
ax2.set_xlabel("Time [s]")

# Adjust layout
plt.tight_layout()
# plt.show()
plt.savefig(f"output/part4/Plot_4_3_A.png", dpi=400)


print(actions["memcached"])



# Create figure and axis
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True,
                               gridspec_kw={'height_ratios': [2, 1]})

# --- Top Plot ---
# Bar plot for QPS (right y-axis)
ax1b = ax1.twinx()
ax1b.bar(time, qps, width=10, color='royalblue', alpha=0.8, label="QPS", zorder=1)
ax1b.set_ylabel("Queries per second (QPS)", color='blue')
ax1b.tick_params(axis='y', labelcolor='blue')
ax1b.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x / 1000)}k'))

# Line plot for latency (left y-axis)
ax1.set_ylim(0, 2.5)
ax1.step(memcached_times, memcached_cores,color='green', label='memcached_cores', zorder=2)
ax1.set_ylabel("Number of cores", color='green')
ax1.tick_params(axis='y', labelcolor='green')

ax1.set_zorder(ax1b.get_zorder() + 1)
ax1.patch.set_visible(False)

# --- Bottom Plot ---
np.random.seed(0)

for i, job in enumerate(jobs):
    prev_time = actions[job][0][0]
    no_cores = actions[job][0][1]

    for action in actions[job][1:]:
        if no_cores == 2:
             bar_height = 0.5
        else:
             bar_height = 1

        y_start = i - bar_height / 2
        y_center = i
        y_range = (y_center - bar_height / 2, bar_height)

        new_time = action[0]
        ax2.broken_barh([(prev_time, new_time-prev_time)], y_range,facecolors=JOB_COLORS[job])
        prev_time = new_time
        
        no_cores = action[-1]

ax2.set_yticks(range(len(jobs)))
ax2.set_yticklabels(jobs)
ax2.set_xlabel("Time [s]")

# Adjust layout
plt.tight_layout()
#plt.show()
plt.savefig(f"output/part4/Plot_4_3_B.png", dpi=400)


