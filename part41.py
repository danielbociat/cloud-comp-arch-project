import os
import subprocess
import re
import time
import argparse
from datetime import datetime
from collections import defaultdict

env = os.environ.copy()

env["PROJECT"] = "cca-eth-2025-group-008"
env["KOPS_STATE_STORE"] = "gs://cca-eth-2025-group-008-ccraciun"




NUM_RUNS = 1

def update_server_config(num_threads, num_cores, memcache_server, memcache_server_internal_ip):
    # update server ip, memory, threads
    subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{memcache_server}", "--zone", "europe-west1-b",
                    "--ssh-key-file", "~/.ssh/cloud-computing",
                    "--command",
                    f"chmod +x ~/update-memcached-server.sh && ~/update-memcached-server.sh {memcache_server_internal_ip} {num_threads}"])

    # restart memcached server
    print("restarting memcached server...")
    subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{memcache_server}", "--zone", "europe-west1-b",
                    "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                    "chmod +x ~/restart-memcached-server.sh && ~/restart-memcached-server.sh"])

    print("check memcached restarted")
    subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{memcache_server}", "--zone", "europe-west1-b",
                    "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                    "chmod +x ~/check-memcached-server.sh && ~/check-memcached-server.sh"], check=True)


def log_run_results(parsec_output, memcached_output):
    pass


def is_job_completed(kubectl_output):
    lines = kubectl_output.strip().splitlines()
    if len(lines) < 2:
        return False

    job_info = lines[1]
    parts = job_info.split()

    completions = parts[2]

    return completions == "1/1"



def extract_times(output):
    match = re.search(r"real\s+(\d+)m([\d.]+)s\s+user\s+(\d+)m([\d.]+)s\s+sys\s+(\d+)m([\d.]+)s", output)

    real_time = int(match.group(1)) * 60 + float(match.group(2))
    user_time = int(match.group(3)) * 60 + float(match.group(4))
    sys_time = int(match.group(5)) * 60 + float(match.group(6))

    print(f"Real time: {real_time} seconds")
    print(f"User time: {user_time} seconds")
    print(f"Sys time: {sys_time} seconds")

    return real_time, user_time, sys_time


def write_run_data(filename, no_threads, job_name, real_time, user_time, sys_time):
    line = f"{no_threads},{job_name},{real_time},{user_time},{sys_time}\n"
    with open(filename, "a") as f:
        f.write(line)


def update_template(filename, node_label, cores, num_threads):
    script_dir = os.path.dirname(__file__)
    rel_path = f"part3/{filename}-template.yaml"
    abs_file_path = os.path.join(script_dir, rel_path)

    with open(abs_file_path) as f:
        schemas = f.read()

    schemas = schemas.replace("<n>", str(num_threads))
    schemas = schemas.replace("<node_label>", node_label)
    schemas = schemas.replace("<cores>", cores)

    script_dir = os.path.dirname(__file__)
    rel_path = f"part3/{filename}.yaml"
    abs_file_path = os.path.join(script_dir, rel_path)

    with open(abs_file_path, "w") as f:
        f.write(schemas)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-setup", action="store_true", default=False, help="Runs without the one time setup")
    return parser.parse_args()


if __name__ == '__main__':
    # Init steps

    args = parse_args()

    if not args.no_setup:
        subprocess.run(["gcloud", "auth", "application-default", "login"], check=True)
        subprocess.run(["gcloud", "init"], check=True)
        subprocess.run(["kops", "create", "-f", "part4.yaml"], env=env, check=True)
        subprocess.run(["kops", "update", "cluster", "part4.k8s.local", "--yes", "--admin"], env=env, check=True)
        subprocess.run(["kops", "validate", "cluster", "--wait", "10m"], env=env, check=True)
        subprocess.run(["kubectl", "get", "nodes", "-o", "wide"], env=env, check=True)

    current_time = datetime.now()
    formatted_time = current_time.strftime("%d-%m-%Y-%H-%M")

    output = subprocess.check_output(["kubectl", "get", "nodes", "-o", "wide"], env=env, text=True)
    lines = output.strip().split("\n")
    for line in lines[1:]:
        if "client-agent-" in line:
            client_agent_internal_ip = line.split()[5]
            client_agent = line.split()[0]
        if "client-measure" in line:
            client_measure = line.split()[0]
        if "memcache-server-" in line:
            memcache_server_internal_ip = line.split()[5]
            memcache_server = line.split()[0]

    print("Client agent: ", client_agent, client_agent_internal_ip)

    #upload scripts to the memcached server machine
    scripts = ["install_memcached_part4_1.sh", "check-memcached-server.sh", "restart-memcached-server.sh", "update-memcached-server.sh"]
    for script in scripts:
        print(f"Uploading script {script} to the server.")
        subprocess.run(
            ["gcloud", "compute", "scp", f"part4/scripts/{script}", f"ubuntu@{memcache_server}:~/",
             "--zone", "europe-west1-b",
             "--ssh-key-file", "~/.ssh/cloud-computing"])
    print("Uploaded shell scripts to the server.")

    # install memcached on the server
    subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{memcache_server}", "--zone", "europe-west1-b",
                    "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                    "chmod +x ~/install_memcached_part4_1.sh && ~/install_memcached_part4_1.sh"])
    print("Installed memcached in the server.")

    #check memcached started
    print("check memcached started")
    subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{memcache_server}", "--zone", "europe-west1-b",
                    "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                    "chmod +x ~/check-memcached-server.sh && ~/check-memcached-server.sh"], check=True)




    # install mcperf in client measure and agent
    if not args.no_setup:
        subprocess.run(
            ["gcloud", "compute", "scp", "update_mcperf.sh", f"ubuntu@{client_agent}:~/", "--zone", "europe-west1-b",
             "--ssh-key-file", "~/.ssh/cloud-computing"])
        print("Uploaded shell script to client")

        subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_agent}", "--zone", "europe-west1-b",
                        "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                        "chmod +x ~/update_mcperf.sh && ~/update_mcperf.sh"])
        print("Updated mcperf in client agent")

    subprocess.Popen(["gcloud", "compute", "ssh", f"ubuntu@{client_agent}", "--zone", "europe-west1-b",
                      "--ssh-key-file", "~/.ssh/cloud-computing", "--quiet", "--command",
                      "cd memcache-perf-dynamic && ./mcperf -T 8 -A"], stdout=subprocess.DEVNULL)
    print("Started mcperf in client agent")

    if not args.no_setup:
        subprocess.run(
            ["gcloud", "compute", "scp", "update_mcperf.sh", f"ubuntu@{client_measure}:~/", "--zone", "europe-west1-b",
             "--ssh-key-file", "~/.ssh/cloud-computing"])
        print("Uploaded shell script to client Measure")

        subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_measure}", "--zone", "europe-west1-b",
                        "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                        "chmod +x ~/update_mcperf.sh && ~/update_mcperf.sh"])
        print("Updated mcperf in client Measure")


    configs = [[1,1], [1,2], [2,1], [2,2]] #[T, C]
    NUM_RUNS = 1
    for i in range(NUM_RUNS):
        for [T, C] in configs:
            update_server_config(num_threads=T, num_cores=C, memcache_server=memcache_server)
            print(f"\n\n\nStart mcperf in client Measure, server has {T} threads and {C} cores.\n\n")
            subprocess.Popen(["gcloud", "compute", "ssh", f"ubuntu@{client_measure}", "--zone", "europe-west1-b",
                                  "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                                  f"cd memcache-perf-dynamic && ./mcperf -s {memcache_server_internal_ip} -a {client_agent_internal_ip} \
                                 --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 --scan 5000:220000:5000 \
                                  > part4/results/results-part4.1-threads{T}-cores{C}-run{i}-{formatted_time}.txt"
                              ],
                             stdout=subprocess.DEVNULL)


    subprocess.run(["kops", "delete", "cluster", "--name", f"part4.k8s.local", "--yes"], check=True)
    print("Successfully deleted cluster!")
