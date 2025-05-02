import json

from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt


MCPERF_OUTPUT_PATH = Path("./data/part3/memcached_results.txt")
JSON_OUTPUT_PATH = Path("./data/part3/res.json")
JOB_COLORS = {
    "parsec-blackscholes": "#CCA000",
    "parsec-canneal": "#CCCCAA",
    "parsec-dedup": "#CCACCA",  
    "parsec-ferret": "#AACCCA", 
    "parsec-freqmine": "#0CCA00",
    "parsec-radix": "#00CCA0",  
    "parsec-vips": "#CC0A00"   
}


def parse_mcperf_output(data_file_path: Path) -> tuple:
    raw_data = None
    with open(data_file_path, "r") as f:
        raw_data = f.readlines()
    
    parsed_data = []
    time_reference = int(raw_data[1].split()[-2]) + 15480000
    for line in raw_data[1:]:
        split = line.split()
        p95 = float(split[12])
        ts_start = (int(split[-2] ) + 15480000 - time_reference) / 1000
        ts_end = (int(split[-1]) + 15480000 - time_reference) / 1000
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
            break
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
    bar_heights = [entry["p95"] for entry in mcperf_data]
    plt.bar(bar_starts, bar_heights, width=bar_widths, align="edge")
    
    plt.xlabel("time")
    plt.ylabel("p95")
    plt.xticks([t for entry in mcperf_data for t in (entry["ts_start"], entry["ts_end"])], rotation=45, fontsize=8)

    for i, job in enumerate(jobs_data):
        y = [100 + 20 * i]
        xmin = (job["started_at"] - time_reference) / 1000
        xmax=(job["finished_at"] - time_reference) / 1000
        color = [JOB_COLORS[job["job_name"]]]
        label = f"{job['job_name']}: {job['node_type']}"
        plt.hlines(y=y, xmin=xmin, xmax=xmax, colors=color, label=label)

    plt.legend()
    plt.show()


def main():
    mcperf_data, time_reference = parse_mcperf_output(MCPERF_OUTPUT_PATH)
    jobs_data = parse_jobs_json(JSON_OUTPUT_PATH)
    plot(mcperf_data, jobs_data, time_reference)


if __name__ == "__main__":
    main()