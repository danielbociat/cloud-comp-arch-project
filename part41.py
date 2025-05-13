import os
import subprocess
import re
import time
import argparse
from datetime import datetime
from collections import defaultdict

env = os.environ.copy()

env["PROJECT"] = "cca-eth-2025-group-008"
env["KOPS_STATE_STORE"] = "gs://cca-eth-2025-group-008-ccraciun/"


NUM_RUNS = 3

def update_server_config(num_threads, num_cores, memcache_server, memcache_server_internal_ip):
    # update server ip, memory, threads, cores
    print("update and restart memcached server...")
    subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{memcache_server}", "--zone", "europe-west1-b",
                    "--ssh-key-file", "~/.ssh/cloud-computing",
                    "--command",
                    f"chmod +x ~/update-memcached-server.sh && ~/update-memcached-server.sh {memcache_server_internal_ip} {num_threads} {num_cores}"])

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-setup", action="store_true", default=False, help="Runs without the one time setup")
    parser.add_argument("--subpart", required=True , default=None, help="Choose: 1a, 1d, 2, 3")
    return parser.parse_args()

def get_container_runtimes(memcache_server, file):
    print("copy runtime results locally")
    subprocess.run(
        ["gcloud", "compute", "scp",
         f"ubuntu@{memcache_server}:~/{file}",
         f"part4/results/subpart2/{file}",
         "--zone", "europe-west1-b",
         "--ssh-key-file", "~/.ssh/cloud-computing"])


if __name__ == '__main__':

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

    if not args.no_setup:
        # upload scripts to the memcached server machine
        scripts = ["install_memcached_part4_1.sh", "check-memcached-server.sh", "update-memcached-server.sh", "measure-cpu-utilisation.sh"]
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


    if args.subpart == "1a":
        configs = [[1,1], [1,2], [2,1], [2,2]] #[T, C]
        for [T, C] in configs:
            update_server_config(num_threads=T,
                                 num_cores=C,
                                 memcache_server=memcache_server,
                                 memcache_server_internal_ip=memcache_server_internal_ip
                                 )
            for i in range(NUM_RUNS):
                print(f"\n\n\nStart run {i} for mcperf in client Measure, server has {T} threads and {C} cores.\n\n")
                subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_measure}", "--zone", "europe-west1-b",
                                "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                                f"cd memcache-perf-dynamic && ./mcperf -s {memcache_server_internal_ip} --loadonly"])
                print("fire")
                subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_measure}", "--zone", "europe-west1-b",
                                      "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                                      f"cd memcache-perf-dynamic && ./mcperf -s {memcache_server_internal_ip} -a {client_agent_internal_ip} \
                                     --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 --scan 5000:220000:5000 \
                                      > ~/results-part4.1-threads{T}-cores{C}-run{i}-{formatted_time}.txt"
                                  ])
                # copy results locally
                print("copy")
                subprocess.run(
                    ["gcloud", "compute", "scp",
                     f"ubuntu@{client_measure}:~/results-part4.1-threads{T}-cores{C}-run{i}-{formatted_time}.txt",
                     f"part4/results/results-part4.1-threads{T}-cores{C}-run{i}-{formatted_time}.txt",
                     "--zone", "europe-west1-b",
                     "--ssh-key-file", "~/.ssh/cloud-computing"])

    elif args.subpart == "1d":
        configs = [[2, 1], [2, 2]]  # [T, C]
        NUM_RUNS = 2
        for [T, C] in configs:
            update_server_config(num_threads=T,
                                 num_cores=C,
                                 memcache_server=memcache_server,
                                 memcache_server_internal_ip=memcache_server_internal_ip
                                 )
            for i in range(1, NUM_RUNS+1):
                print(f"\n\n\nStart run {i} for mcperf in client Measure, server has {T} threads and {C} cores.\n\n")
                subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_measure}", "--zone", "europe-west1-b",
                                "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                                f"cd memcache-perf-dynamic && ./mcperf -s {memcache_server_internal_ip} --loadonly"])

                print("start measuring the CPU utilisation on the memcached server")
                cpu_log_remote = f"cpu-utilisation-{T}threads-{C}cpu-run{i}-{formatted_time}.txt"
                subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{memcache_server}", "--zone", "europe-west1-b",
                                "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                                f"nohup bash -c 'chmod +x ~/measure-cpu-utilisation.sh && ~/measure-cpu-utilisation.sh {cpu_log_remote}' > /dev/null 2>&1 < /dev/null &"
                                ], stdout=subprocess.PIPE)

                print("fire")

                subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_measure}", "--zone", "europe-west1-b",
                                "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                                f"cd memcache-perf-dynamic \
                                        && ./mcperf -s {memcache_server_internal_ip} -a {client_agent_internal_ip} \
                                        --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 --scan 5000:220000:5000 \
                                      > ~/results-part4.1-threads{T}-cores{C}-run{i}-{formatted_time}.txt"
                                ])
                # copy results locally
                print("copy qps")
                subprocess.run(
                    ["gcloud", "compute", "scp",
                     f"ubuntu@{client_measure}:~/results-part4.1-threads{T}-cores{C}-run{i}-{formatted_time}.txt",
                     f"part4/results/d/results-part4.1-threads{T}-cores{C}-run{i}-{formatted_time}.txt",
                     "--zone", "europe-west1-b",
                     "--ssh-key-file", "~/.ssh/cloud-computing"])

                print("copy CPU usage")
                subprocess.run(
                    ["gcloud", "compute", "scp",
                     f"ubuntu@{memcache_server}:~/{cpu_log_remote}",
                     f"part4/results/d/{cpu_log_remote}",
                     "--zone", "europe-west1-b",
                     "--ssh-key-file", "~/.ssh/cloud-computing"])

                print("Delete CPU measuring script...")

                subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{memcache_server}", "--zone", "europe-west1-b",
                                "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                                f"pkill -f measure-cpu-utilisation.sh"
                                ])
    elif args.subpart == "2":
        container_runtime_file = f"container-runtime-{formatted_time}.txt"
        qps_file = f"~/results-part4.2-{formatted_time}.txt"

        if not args.no_setup:
            print("Upload controller on the server...")
            subprocess.run(
                ["gcloud", "compute", "scp", "controller.py", f"ubuntu@{memcache_server}:~/", "--zone", "europe-west1-b",
                 "--ssh-key-file", "~/.ssh/cloud-computing"])
            print("Uploaded controller script to memcached server")

            subprocess.run(
                ["gcloud", "compute", "scp", "scheduler_logger.py", f"ubuntu@{memcache_server}:~/", "--zone", "europe-west1-b",
                 "--ssh-key-file", "~/.ssh/cloud-computing"])
            print("Uploaded scheduler_logger script to memcached server")

            subprocess.run(
                ["gcloud", "compute", "scp", "requirements.txt", f"ubuntu@{memcache_server}:~/", "--zone", "europe-west1-b",
                 "--ssh-key-file", "~/.ssh/cloud-computing"])
            print("Uploaded requirements.txt to memcached server")

            print("Loading memcached")

            print("update server")
            update_server_config(num_threads=2,
                                 num_cores=2,
                                 memcache_server=memcache_server,
                                 memcache_server_internal_ip=memcache_server_internal_ip
                                 )
            print(memcache_server_internal_ip)
        subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_measure}", "--zone", "europe-west1-b",
                        "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                        f"cd memcache-perf-dynamic && ./mcperf -s {memcache_server_internal_ip} --loadonly"])
        print("Fire in the background...")

        remote_mcperf_cmd = (
            f"nohup ~/memcache-perf-dynamic/mcperf "
            f"-s {memcache_server_internal_ip} "
            f"-a {client_agent_internal_ip} "
            "--noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 900 "
            "--qps_interval 10 --qps_min 5000 --qps_max 180000 "
            f"> {qps_file} 2>&1 < /dev/null &"
        )

        subprocess.run([
            "gcloud", "compute", "ssh", f"ubuntu@{client_measure}",
            "--zone", "europe-west1-b",
            "--ssh-key-file", "~/.ssh/cloud-computing",
            "--command", remote_mcperf_cmd
        ])

        print("Start the controller...")

        subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{memcache_server}", "--zone", "europe-west1-b",
                        "--ssh-key-file", "~/.ssh/cloud-computing", "--command",
                        f"bash -c 'sudo apt-get install python3-pip && \
                        sudo pip install --break-system-packages -r requirements.txt && \
                        sudo usermod -aG docker $USER && \
                          sudo apt install -y docker.io && \
                          sudo python3 -u controller.py {container_runtime_file}'"])

        get_container_runtimes(memcache_server, container_runtime_file)


        print("copy qps results locally")
        subprocess.run(
            ["gcloud", "compute", "scp",
             f"ubuntu@{client_measure}:{qps_file}",
             f"part4/results/subpart2/results-part4.2-{formatted_time}.txt",
             "--zone", "europe-west1-b",
             "--ssh-key-file", "~/.ssh/cloud-computing"])


    subprocess.run(["kops", "delete", "cluster", "--name", f"part4.k8s.local", "--yes"], check=True)
    print("Successfully deleted cluster!")
