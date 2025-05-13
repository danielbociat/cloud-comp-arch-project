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

threads = [1, 2, 4, 8]
jobs = ["blackscholes", "canneal", "dedup", "ferret", "freqmine", "radix", "vips"] 

nodes = ["node-a-2core", "node-b-2core", "node-c-4core", "node-d-4core"]
# node-a-2core - e2-highmem-2 - 2 cpus, 16 gb
# node-b-2core - n2-highcpu-2 - 2 cpus, 2 gb
# node-c-4core - c3-highcpu-4 - 4 cpus, 8 gb
# node-d-4core - n2-standard-4 - 4 cpus, 16 gb

config = {
    "radix" : (nodes[0],"0", 8),
    "memcached" : (nodes[0],"1", 1),

    "blackscholes" : (nodes[1],"0,1", 2),
    "dedup" : (nodes[1],"0,1", 8),
    
    "freqmine" : (nodes[2],"0,1,2,3", 8),
    "vips" : (nodes[2],"0,1,2,3", 6),

    "canneal" : (nodes[3],"0,1,2,3", 8),
    "ferret" : (nodes[3],"0,1,2,3", 6),
}

NUM_RUNS = 1

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

def is_pod_ready(kubectl_output):
    lines = kubectl_output.strip().splitlines()
    if len(lines) < 2:
        return False 

    pod_info = lines[1]
    parts = pod_info.split()

    readiness = parts[1]

    return readiness == "1/1"

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
        subprocess.run(["kops", "create", "-f", "part3.yaml"], env=env, check=True)
        subprocess.run(["kops", "update", "cluster", "part3.k8s.local", "--yes", "--admin"], env=env, check=True)
        subprocess.run(["kops", "validate", "cluster", "--wait", "10m"],  env=env, check=True)
        subprocess.run(["kubectl", "get", "nodes", "-o", "wide"], env=env, check=True)
    # # else:
    #     print("WORKS")

    current_time = datetime.now()
    formatted_time = current_time.strftime("%d-%m-%Y-%H-%M")    

    output = subprocess.check_output(["kubectl", "get", "nodes", "-o", "wide"], env=env, text=True)
    lines = output.strip().split("\n")
    for line in lines[1:]:
        if "client-agent-a-" in line:
            client_agent_a_internal_ip = line.split()[5]
            client_agent_a = line.split()[0]
        if "client-agent-b-" in line:
            client_agent_b_internal_ip = line.split()[5]
            client_agent_b = line.split()[0]
        if "client-measure" in line:
            client_measure = line.split()[0]

    print("A: ", client_agent_a, client_agent_a_internal_ip)
    print("B: ", client_agent_b, client_agent_b_internal_ip)
    
    for job in jobs:
        update_template(job, config[job][0], config[job][1], config[job][2])
    update_template("memcached", config["memcached"][0], config["memcached"][1], config["memcached"][2])


    subprocess.run(["kubectl", "create", "-f", f"part3/memcached.yaml"], env=env, check=True)
    subprocess.run(["kubectl", "expose", "pod", "some-memcached", "--name", "some-memcached-11211",
                    "--type", "LoadBalancer", "--port", "11211", "--protocol", "TCP"], env=env, check=True)

    output = subprocess.check_output(["kubectl", "get", "pods", "--selector=name=some-memcached", "-o", "wide"], env=env, text=True)
    while not is_pod_ready(output):
        print("Memcached not ready yet...")
        time.sleep(30)
        output = subprocess.check_output(["kubectl", "get", "pods", "--selector=name=some-memcached", "-o", "wide"], env=env, text=True)
    
    lines = output.strip().split("\n")
    for line in lines:
        print(line)
        if "memcache" in line:
            memcached_ip = line.split()[5]
    print("MEMCACHED_IP: ", memcached_ip)

    print("Memcached running!")

    if not args.no_setup:
        subprocess.run(["gcloud", "compute", "scp", "update_mcperf.sh",  f"ubuntu@{client_agent_a}:~/", "--zone", "europe-west1-b", 
                        "--ssh-key-file", "~/.ssh/cloud-computing"])
        print("Uploaded shell script to client A")

        subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_agent_a}", "--zone", "europe-west1-b", 
                        "--ssh-key-file", "~/.ssh/cloud-computing", "--command", "chmod +x ~/update_mcperf.sh && ~/update_mcperf.sh"])
        print("Updated mcperf in client A")

    subprocess.Popen(["gcloud", "compute", "ssh", f"ubuntu@{client_agent_a}", "--zone", "europe-west1-b", 
                    "--ssh-key-file", "~/.ssh/cloud-computing", "--quiet", "--command", "cd memcache-perf-dynamic && ./mcperf -T 2 -A"], stdout=subprocess.DEVNULL)
    print("Started mcperf in client A")

    if not args.no_setup:
        subprocess.run(["gcloud", "compute", "scp", "update_mcperf.sh",  f"ubuntu@{client_agent_b}:~/", "--zone", "europe-west1-b", 
                        "--ssh-key-file", "~/.ssh/cloud-computing"])
        print("Uploaded shell script to client B")

        subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_agent_b}", "--zone", "europe-west1-b", 
                        "--ssh-key-file", "~/.ssh/cloud-computing", "--command", "chmod +x ~/update_mcperf.sh && ~/update_mcperf.sh"])
        print("Updated mcperf in client B")
    
    subprocess.Popen(["gcloud", "compute", "ssh", f"ubuntu@{client_agent_b}", "--zone", "europe-west1-b", 
                    "--ssh-key-file", "~/.ssh/cloud-computing", "--quiet", "--command", "cd memcache-perf-dynamic && ./mcperf -T 4 -A"], stdout=subprocess.DEVNULL)
    print("Started mcperf in client B")

    if not args.no_setup:
        subprocess.run(["gcloud", "compute", "scp", "update_mcperf.sh",  f"ubuntu@{client_measure}:~/", "--zone", "europe-west1-b", 
                        "--ssh-key-file", "~/.ssh/cloud-computing"])
        print("Uploaded shell script to client Measure")

        subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_measure}", "--zone", "europe-west1-b", 
                        "--ssh-key-file", "~/.ssh/cloud-computing", "--command", "chmod +x ~/update_mcperf.sh && ~/update_mcperf.sh"])
        print("Updated mcperf in client Measure")
    
    subprocess.run(["gcloud", "compute", "ssh", f"ubuntu@{client_measure}", "--zone", "europe-west1-b", 
                    "--ssh-key-file", "~/.ssh/cloud-computing", "--command", f"cd memcache-perf-dynamic && ./mcperf -s {memcached_ip} --loadonly"])
    subprocess.Popen(["gcloud", "compute", "ssh", f"ubuntu@{client_measure}", "--zone", "europe-west1-b", 
                    "--ssh-key-file", "~/.ssh/cloud-computing", "--command", f"cd memcache-perf-dynamic && ./mcperf -s {memcached_ip} -a {client_agent_a_internal_ip} \
                        -a {client_agent_b_internal_ip} --noload -T 6 -C 4 -D 4 -Q 1000 -c 4 -t 10 --scan 30000:30500:5 > results.txt"], stdout=subprocess.DEVNULL)
    print("Started mcperf in client Measure")


    # Run the processes
    for i in range(NUM_RUNS):
        completed_jobs = set()
        RUNNING_JOBS = defaultdict(lambda: "")

        while True:
            for job in jobs:
                if job in completed_jobs: continue

                if RUNNING_JOBS[(config[job][0], config[job][1])] == "":
                    print("Scheduled: ", job)
                    subprocess.run(["kubectl", "create", "-f", f"part3/{job}.yaml"], env=env, check=True)
                    RUNNING_JOBS[(config[job][0], config[job][1])] = job
                else:
                    running_job = RUNNING_JOBS[(config[job][0], config[job][1])]
                    result = subprocess.run(
                        ["kubectl", "get", "job", running_job, "-o", "jsonpath={.status.succeeded}"],
                        capture_output=True, text=True
                    )

                    if result.stdout.strip() == "1":
                        print(running_job, "completed")
                        completed_jobs.add(running_job)
                        
                        if job in completed_jobs: continue

                        print("Scheduled: ", job)
                        subprocess.run(["kubectl", "create", "-f", f"part3/{job}.yaml"], env=env, check=True)
                        RUNNING_JOBS[(config[job][0], config[job][1])] = job
                    else:
                        time.sleep(1)
                        continue

            if len(completed_jobs) == len(jobs): break
            
        with open(f"results-jobs-{i}-{formatted_time}.json", "w") as outfile:
            subprocess.run(["kubectl", "get", "pods", "-o", "json"], env=env, stdout=outfile, check=True)
        
        with open(f"results-config-{formatted_time}.txt", "w") as outfile:
            for job in jobs:
                outfile.write(job, config[job])
        subprocess.run(["python3", "get_time.py", f"results-jobs-{i}-{formatted_time}.json"], check=True)
   
        subprocess.run(["gcloud", "compute", "scp", f"ubuntu@{client_measure}:~/memcache-perf-dynamic/results.txt", f"memcached_results_{formatted_time}.txt", "--zone", "europe-west1-b", 
                "--ssh-key-file", "~/.ssh/cloud-computing"])

        log_run_results(f"results-jobs-{i}.json", f"memcached_results_{formatted_time}.txt")

    # Make sure there are no witnesses
    subprocess.run(["kubectl", "delete", "jobs", "--all"])
    subprocess.run(["kubectl", "delete", "pods", "--all"])
    subprocess.run(["kubectl", "delete", "services", "some-memcached-11211"])


    # subprocess.run(["kops", "delete", "cluster", "--name", f"part3.k8s.local", "--yes"], check=True)
    # print("Successfully deleted cluster!")
