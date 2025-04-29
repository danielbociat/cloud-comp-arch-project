from collections import defaultdict

intereferences = ["None", "cpu", "l1d", "l1i", "l2", "llc", "membw"]
workloads = defaultdict(dict)

if __name__ == "__main__":

    with open("part2a-output-26-04-2025-19-35.csv", "r") as f:
        for line in f:
            interference, workload, real_time, _, _ = line.split(",")
            workloads[workload][interference] = float(real_time)

    print("\t\t\t",end=" ")
    for intf in intereferences:
        print(intf, end="  ")
    print()

    for workload_name in workloads.keys():
        print(workload_name, end = " ")
        workload = workloads[workload_name]
        for interference in intereferences:
            print("%.2f" % (workload[interference] / workload['None']), end = " ")
        print()

    for workload_name in workloads.keys():
        workload = workloads[workload_name]
        for interference in intereferences[1:]:
            ratio = workload[interference] / workload['None']
            colour = "Green" if ratio <=1.3 else "YellowOrange" if ratio <=2 else "Red"
            output = "& \cellcolor{" + colour + "}"
            print(output, end = " ")
        print()






