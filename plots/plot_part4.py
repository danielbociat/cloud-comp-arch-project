import os
from pathlib import Path

import matplotlib.pyplot as plt


MCPERF_OUTPUT_1A_PATH = Path("./data/part4/1a/")
NUM_RUNS = 3


class ResultData:
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

    def compute_averages_and_errors(self):
        num_points = len(self.qps[0])
        self.qps_averages = [0 for _ in range(num_points)]
        self.p95_averages = [0 for _ in range(num_points)]
        self.qps_errors = [0 for _ in range(num_points)]
        self.p95_errors = [0 for _ in range(num_points)]
        for run in range(self.num_runs):
            for i in range(num_points):
                self.qps_averages[i] += self.qps[run][i]
                self.p95_averages[i] += self.p95[run][i]
        
        self.qps_averages = [val / self.num_runs for val in self.qps_averages]
        self.p95_averages = [val / self.num_runs for val in self.p95_averages]

        for run in range(self.num_runs):
            for i in range(num_points):
                qps_diff = abs(self.qps_averages[i] - self.qps[run][i])
                if qps_diff > self.qps_errors[i]:
                    self.qps_errors[i] = qps_diff

                p95_diff = abs(self.p95_averages[i] - self.p95[run][i])
                if p95_diff > self.p95_errors[i]:
                    self.p95_errors[i] = p95_diff
        
    def get_plot_values(self) -> tuple:
        self.compute_averages_and_errors()
        return self.qps_averages, self.p95_averages, self.qps_errors, self.p95_errors


def parse_mcperf_output(output_path: Path) -> dict:
    file_results = os.listdir(output_path)
    results = {} # key is a tuple of the form (num_threads, num_cores) and value is ResultData

    for file_result in file_results:
        split = file_result.split("-")
        threads = int(split[2][-1])
        cores = int(split[3][-1])
        num_run = int(split[4][-1])
        if (threads, cores) not in results:
            results[(threads, cores)] = ResultData(NUM_RUNS)
        current_file = os.path.join(output_path, file_result)
        with open(current_file, "r") as f:
            lines = f.readlines()
            for line in lines:
                line_split = line.split()
                if line_split[0] == "read":
                    p95 = float(line_split[12])
                    qps = float(line_split[16])
                    results[(threads, cores)].add_qps(num_run, qps)
                    results[(threads, cores)].add_p95(num_run, p95)

    return results


def plot_41a(results: dict):
    plt.figure(figsize=(14, 8))

    for k in results:
        x, y, xerr, yerr = results[k].get_plot_values()
        threads_label = "1 thread" if k[0] == 1 else "2 threads"
        cores_label = "1 core" if k[1] == 1 else "2 cores"
        plt.errorbar(x, y, yerr, xerr, capsize=4, elinewidth=1.5, markersize=4, label=f"{threads_label}, {cores_label}")

    # plt.ylim(0, 1000)
    plt.xlabel("QPS")
    plt.ylabel("p95")
    plt.title("p95 vs QPS for Each Configuration\nAveraged over 3 runs")
    plt.grid(True)
    plt.legend()
    plt.show()


def main():
    results = parse_mcperf_output(MCPERF_OUTPUT_1A_PATH)
    plot_41a(results)


if __name__ == "__main__":
    main()