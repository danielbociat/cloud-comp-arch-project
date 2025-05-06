import os
import math
import csv

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


MCPERF_OUTPUT_1A_PATH = Path("./data/part4/1a/")
DATA_OUTPUT_1D_PATH = Path("./data/part4/1d/")
NUM_RUNS = 1


class McperfResultData:
    def __init__(self, num_runs: int):
        self.num_runs = num_runs
        self.qps = [[] for _ in range(num_runs)]
        self.qps_averages = None
        self.p95 = [[] for _ in range(num_runs)]
        self.p95_averages = None
        self.qps_errors = None
        self.p95_errors = None
    
    def add_qps(self, run: int, val: float):
        self.qps[run].append(val)
    
    def add_p95(self, run: int, val: float):
        self.p95[run].append(val)

    def compute_averages_and_errors(self, std_dev=True):
        num_points = len(self.qps[0])
        self.qps_averages = [0 for _ in range(num_points)]
        self.p95_averages = [0 for _ in range(num_points)]
        self.qps_errors = [0 for _ in range(num_points)]
        self.p95_errors = [0 for _ in range(num_points)]

        if self.num_runs == 1:
            self.qps_averages = self.qps[0]
            self.p95_averages = self.p95[0]
            return 

        for run in range(self.num_runs):
            for i in range(num_points):
                self.qps_averages[i] += self.qps[run][i]
                self.p95_averages[i] += self.p95[run][i]
        
        self.qps_averages = [val / self.num_runs for val in self.qps_averages]
        self.p95_averages = [val / self.num_runs for val in self.p95_averages]

        if not std_dev: # error is max deviation
            for run in range(self.num_runs):
                for i in range(num_points):
                    qps_diff = abs(self.qps_averages[i] - self.qps[run][i])
                    if qps_diff > self.qps_errors[i]:
                        self.qps_errors[i] = qps_diff

                    p95_diff = abs(self.p95_averages[i] - self.p95[run][i])
                    if p95_diff > self.p95_errors[i]:
                        self.p95_errors[i] = p95_diff
        else:
            for i in range(num_points):
                qps_vals = [self.qps[run][i] for run in range(self.num_runs)]
                p95_vals = [self.p95[run][i] for run in range(self.num_runs)]

                qps_mean = self.qps_averages[i]
                p95_mean = self.p95_averages[i]

                qps_var = sum((val - qps_mean) ** 2 for val in qps_vals) / (self.num_runs - 1)
                p95_var = sum((val - p95_mean) ** 2 for val in p95_vals) / (self.num_runs - 1)

                self.qps_errors[i] = math.sqrt(qps_var)
                self.p95_errors[i] = math.sqrt(p95_var)

                    
    def get_plot_values(self) -> tuple:
        self.compute_averages_and_errors()
        return self.qps_averages, self.p95_averages, self.qps_errors, self.p95_errors


def parse_mcperf_output(output_path: Path) -> dict:
    file_results = os.listdir(output_path)
    results = {} # key is a tuple of the form (num_threads, num_cores) and value is ResultData

    for file_result in file_results:
        split = file_result.split("-")
        if split[0] != "cpu":
            threads = int(split[2][-1])
            cores = int(split[3][-1])
            num_run = int(split[4][-1])
            if (threads, cores) not in results:
                results[(threads, cores)] = McperfResultData(NUM_RUNS)
            current_file = os.path.join(output_path, file_result)
            with open(current_file, "r") as f:
                lines = f.readlines()
                for line in lines:
                    line_split = line.split()
                    if line_split[0] == "read":
                        p95 = float(line_split[12])
                        qps = float(line_split[16])
                        results[(threads, cores)].add_qps(num_run, qps)
                        results[(threads, cores)].add_p95(num_run, float(p95 / 1000))

    return results


def parse_cpu_util_output(data_file_path: Path) -> list:
    reader = None
    # format:
    # [(ts, cpu)]
    data = []
    with open(data_file_path) as csv_file:
        reader = csv.reader(csv_file, delimiter=',')
        for row in reader:
            # print(row)
            if "Time" not in row[0]:
                ts = int(row[0])
                cpu = float(row[1]) / 25.0
                # data["times"].append(ts)
                # data["cpu"].append(cpu)
                data.append((ts, cpu))
    return data


def parse_mcperf_timestamps(data_file_path: Path) -> list:
    intervals = [] # list of tuples: (ts_start, ts_end)

    with open(data_file_path, "r") as f:
        lines = f.readlines()
        for line in lines:
            line_split = line.split()
            if line_split[0] == "read":
                ts_start = int(line_split[-2])
                ts_end = int(line_split[-1])
                intervals.append((ts_start, ts_end))
    
    return intervals


def get_cpu_usage(data_path: Path) -> dict:
    files = os.listdir(data_path)
    results = {}

    # parse files
    for file in files:
        split = file.split("-")
        file_path = os.path.join(data_path, file)
        
        if split[0] == "cpu":
            num_threads = int(split[2][0])
            num_cores = int(split[3][0])
            parsed_cpu_util = parse_cpu_util_output(file_path)

            if (num_threads, num_cores) not in results:
                results[(num_threads, num_cores)] = {}
            results[(num_threads, num_cores)]["cpu_util_timestamps"] = parsed_cpu_util
        else:
            num_threads = int(split[2][-1])
            num_cores = int(split[3][-1])
            parsed_timestamps = parse_mcperf_timestamps(file_path)

            if (num_threads, num_cores) not in results:
                results[(num_threads, num_cores)] = {}
            results[(num_threads, num_cores)]["mcperf_timestamps"] = parsed_timestamps


    # match cpu usage timestamps with mcperf load intervals
    for key in results:
        cpu_usages = []
        for ts_start, ts_end in results[key]["mcperf_timestamps"]:
            for ts, cpu in results[key]["cpu_util_timestamps"]:
                if ts >= ts_start and ts <= ts_end:
                    cpu_usages.append(cpu)

        results[key]["cpu_usage"] = cpu_usages

    return results


def plot_41a(results: dict):
    plt.figure(figsize=(14, 8))
    ax = plt.gca()

    for k in results:
        x, y, xerr, yerr = results[k].get_plot_values()
        threads_label = "1 thread" if k[0] == 1 else "2 threads"
        cores_label = "1 core" if k[1] == 1 else "2 cores"
        plt.errorbar(x, y, yerr, xerr, capsize=4, elinewidth=1.5, markersize=4, label=f"{threads_label}, {cores_label}")

    ax.xaxis.set_major_locator(ticker.MultipleLocator(10000))
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x / 1000)}k"))

    ax.yaxis.set_major_locator(ticker.MultipleLocator(0.1))
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.1f"))

    plt.xlim(0, 230000)
    plt.xlabel("QPS")
    plt.ylabel("p95 (ms)", rotation=0, labelpad=40)
    plt.title("p95 vs QPS for Each Configuration\nAveraged over 3 runs")
    plt.grid(True)
    plt.tight_layout()
    plt.legend()
    plt.show()


def plot_41d(mcperf_results: dict, cpu_usage_results: dict):
    for threads, cores in mcperf_results:
        qps, p95, _, _ = mcperf_results[(threads, cores)].get_plot_values()
        cpu_usage = cpu_usage_results[(threads, cores)]["cpu_usage"]

        fig, ax1 = plt.subplots(figsize=(14, 8))
        fig.set_dpi(300)
        line1, = ax1.plot(qps, p95, "go-",  label='p95')
        ax1.set_xlabel('QPS')
        ax1.set_ylabel('p95 (ms)')
        ax1.tick_params(axis='y')

        ax2 = ax1.twinx()
        line2, = ax2.plot(qps, cpu_usage, "bs--", label='cpu usage')
        ax2.set_ylabel('cpu usage')
        ax2.tick_params(axis='y')

        ax1.xaxis.set_major_locator(ticker.MultipleLocator(10000))
        ax1.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x / 1000)}k"))

        ax1.yaxis.set_major_locator(ticker.MultipleLocator(0.1))
        ax1.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.1f"))

        slo_line = ax1.axhline(y=0.8, color='red', linestyle='--', linewidth=1, label='SLO (0.8 ms)')

        ax1.grid(True, which='both', axis='both')

        handles = [line1, slo_line, line2]
        labels = [h.get_label() for h in handles]
        ax1.legend(handles, labels, loc='upper left')

        plt.xlim(0, 230000)
        plt.title(f"p95 and CPU Usage Versus QPS\n{threads} threads, {cores} cores")
        fig.tight_layout()  # To prevent label cutoff

        #plt.show()
        plt.savefig(f"{threads}_threads_{cores}_cores.png", dpi=400)


def main():
    # results = parse_mcperf_output(MCPERF_OUTPUT_1A_PATH)
    # plot_41a(results)
    mcperf_results = parse_mcperf_output(DATA_OUTPUT_1D_PATH)
    cpu_usage_results = get_cpu_usage(DATA_OUTPUT_1D_PATH)
    plot_41d(mcperf_results, cpu_usage_results)


if __name__ == "__main__":
    main()