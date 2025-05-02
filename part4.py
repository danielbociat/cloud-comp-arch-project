import os
import subprocess
import re
import time
import argparse
from datetime import datetime
from collections import defaultdict

env = os.environ.copy()

env["PROJECT"] = "cca-eth-2025-group-008"
env["KOPS_STATE_STORE"] = "gs://cca-eth-2025-group-008-dbociat"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-setup", action="store_true", default=False, help="Runs without the one time setup")
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()

    if not args.no_setup:
        subprocess.run(["sudo", "usermod", "-a", "-G", "docker", "$(whoami)"])
        subprocess.run(["gcloud", "auth", "application-default", "login"], check=True)
        subprocess.run(["gcloud", "init"], check=True)
        subprocess.run(["kops", "create", "-f", "part3.yaml"], env=env, check=True)
        subprocess.run(["kops", "update", "cluster", "part3.k8s.local", "--yes", "--admin"], env=env, check=True)
        subprocess.run(["kops", "validate", "cluster", "--wait", "10m"],  env=env, check=True)

    output = subprocess.check_output(["kubectl", "get", "nodes", "-o", "wide"], env=env, text=True)
    lines = output.strip().split("\n")
    for line in lines[1:]:
        if "memcache-server" in line:
            memcache_internal_ip = line.split()[5]
            memcache_server_name = line.split()[0]
        if "client-agent-a-" in line:
            client_agent_a_internal_ip = line.split()[5]
            client_agent_a = line.split()[0]
        if "client-measure" in line:
            client_measure = line.split()[0]
        
    
    if not args.no_setup:
        subprocess.run(["gcloud", "compute", "scp", "update_mcperf.sh",  f"ubuntu@{client_agent_a}:~/", "--zone", "europe-west1-b", 
                        "--ssh-key-file", "~/.ssh/cloud-computing"])
        print("Uploaded shell script to client A")

        subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_agent_a}", "--zone", "europe-west1-b", 
                        "--ssh-key-file", "~/.ssh/cloud-computing", "--command", "chmod +x ~/update_mcperf.sh && ~/update_mcperf.sh"])
        print("Updated mcperf in client A")

    subprocess.Popen(["gcloud", "compute", "ssh", f"ubuntu@{client_agent_a}", "--zone", "europe-west1-b", 
                    "--ssh-key-file", "~/.ssh/cloud-computing", "--quiet", "--command", "cd memcache-perf-dynamic && ./mcperf -T 8 -A"], stdout=subprocess.DEVNULL)
    print("Started mcperf in client A")

    if not args.no_setup:
        subprocess.run(["gcloud", "compute", "scp", "update_mcperf.sh",  f"ubuntu@{client_measure}:~/", "--zone", "europe-west1-b", 
                        "--ssh-key-file", "~/.ssh/cloud-computing"])
        print("Uploaded shell script to client Measure")

        subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_measure}", "--zone", "europe-west1-b", 
                        "--ssh-key-file", "~/.ssh/cloud-computing", "--command", "chmod +x ~/update_mcperf.sh && ~/update_mcperf.sh"])
        print("Updated mcperf in client Measure")
    
    subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_measure}", "--zone", "europe-west1-b", 
                    "--ssh-key-file", "~/.ssh/cloud-computing", "--command", f"cd memcache-perf-dynamic && ./mcperf -s {memcache_internal_ip} --loadonly"])
    subprocess.Popen(["gcloud", "compute", "ssh", f"ubuntu@{client_measure}", "--zone", "europe-west1-b", 
                    "--ssh-key-file", "~/.ssh/cloud-computing", "--command", f"cd memcache-perf-dynamic && ./mcperf -s {memcache_internal_ip} -a {client_agent_a_internal_ip} \
                    --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 10 --qps_interval 2 --qps_min 5000 --qps_max 180000 > results.txt"], stdout=subprocess.DEVNULL)
    print("Started mcperf in client Measure")


    # subprocess.run(["kops", "delete", "cluster", "--name", f"part4.k8s.local", "--yes"], check=True)
    # print("Successfully deleted cluster!")