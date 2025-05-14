import json

from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


MCPERF_OUTPUT_PATH = Path("./data/part3/memcached_results.txt")
JSON_OUTPUT_PATH = Path("./data/part3/res.json")
JOB_COLORS = {
    "blackscholes": "#CCA000",
    "canneal": "#CCCCAA",
    "dedup": "#CCACCA",  
    "ferret": "#AACCCA", 
    "freqmine": "#0CCA00",
    "radix": "#00CCA0",  
    "vips": "#CC0A00"   
}


def parse_mcperf_output(data_file_path: Path) -> tuple:
    raw_data = None
    with open(data_file_path, "r") as f:
        raw_data = f.readlines()
    
    parsed_data = []
    time_reference = int(raw_data[1].split()[-2])
    for line in raw_data[1:]:
        split = line.split()
        p95 = float(split[12])
        ts_start = (int(split[-2] ) - time_reference) / 1000
        ts_end = (int(split[-1]) - time_reference) / 1000
        parsed_data.append(
            {
                "p95": p95,
                "ts_start": ts_start,
                "ts_end": ts_end
            }
        )
    return parsed_data, time_reference


def parse_jobs_json(jobs_json_path: Path) -> dict:
    jobs_json = None
    with open(jobs_json_path, "r") as f:
        jobs_json = json.load(f)
    
    parsed_data = []
    for item in jobs_json["items"]:
        job_name = item["metadata"]["labels"].get("job-name")
        
        if job_name is None:
            continue
        started_at = item["status"]["containerStatuses"][0]["state"]["terminated"]["startedAt"]
        finished_at = item["status"]["containerStatuses"][0]["state"]["terminated"]["finishedAt"]

        dt = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ")
        dt = dt.replace(tzinfo=timezone.utc)
        started_at_ts = dt.timestamp() * 1000 # ms
        
        
        dt = datetime.strptime(finished_at, "%Y-%m-%dT%H:%M:%SZ")
        dt = dt.replace(tzinfo=timezone.utc) 
        finished_at_ts = dt.timestamp() * 1000 # ms

        node_type = item["spec"]["nodeSelector"]["cca-project-nodetype"]
        parsed_data.append(
            {
                "job_name": job_name,
                "node_type": node_type,
                "started_at": started_at_ts,
                "finished_at": finished_at_ts
            }
        )

    return parsed_data


def plot(mcperf_data: list, jobs_data: list, time_reference: int):
    plt.figure(figsize=(14, 8))

    bar_starts = [entry["ts_start"] for entry in mcperf_data]
    bar_widths = [entry["ts_end"] - entry["ts_start"] for entry in mcperf_data]
    bar_heights = [entry["p95"] / 1000 for entry in mcperf_data]
    plt.bar(bar_starts, bar_heights, width=bar_widths, align="edge")
    
    plt.xlabel("time")
    
    plt.ylabel("p95")
    plt.ylim(0, 1)
    plt.yticks(np.arange(0, 1.3, 0.2))
    # plt.yticklabels([f'{int(tick * 1000)}' for tick in np.arange(0, 1.1, 0.1)])

    plt.axhline(y=1, color='black', linestyle='dotted', linewidth=1.5, label='SLO (1 ms)')

    #plt.xticks([t for entry in mcperf_data for t in (entry["ts_start"], entry["ts_end"])], rotation=45, fontsize=8)
    plt.xticks(np.arange(0, 220, 20))


    plt.legend()
    plt.show()


    plt.figure(figsize=(14, 4))

    y_curr = 0.05

    jobs_data = sorted(jobs_data, key= lambda d: d["node_type"])

    for job in jobs_data:
        
        print(job)
        y = [y_curr]
        xmin = (job["started_at"] - time_reference) / 1000
        xmax=(job["finished_at"] - time_reference) / 1000

        print(xmin, xmax)
        color = [JOB_COLORS[job["job_name"]]]
        label = f"{job['job_name']}: {job['node_type']}"
        plt.hlines(y=y, xmin=xmin, xmax=xmax, colors=color, label=label, linewidth=25, linestyles='solid')
        print((job["started_at"]  + job["finished_at"] - 2* time_reference)/1000 / 2)
        plt.text((job["started_at"]  + job["finished_at"]- 2* time_reference)/1000 / 2,
            y_curr,
            job["job_name"] + " | " + job["node_type"] + f" ({(job["finished_at"] - job["started_at"])/1000} s)",
            ha='center', va='center', fontsize=7, color='black')
        
        y_curr += 0.05
    plt.xticks(np.arange(0, 220, 20))
    plt.yticks([])

    plt.show()

def main():
    mcperf_data, time_reference = parse_mcperf_output(MCPERF_OUTPUT_PATH)
    jobs_data = parse_jobs_json(JSON_OUTPUT_PATH)
    plot(mcperf_data, jobs_data, time_reference)


if __name__ == "__main__":
    main()