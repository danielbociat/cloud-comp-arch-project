import sys
import time
import subprocess

import docker
import psutil

import scheduler_logger


MEMCACHED_PROCESS = "memcached"


class Controller:
    def __init__(self, log_file):
        self.docker_client = docker.from_env()
        self.finished = list()
        self.memcached_single_core = True
        self.memcached_num_cores = 2

        # thresholds
        self.T_mcd_1core = 25
        self.T_mcd_2core_low = 40
        self.T_mcd_2core_high = 150
        self.T1_cpu = 50
        self.T2_cpu = 80

        self.logger = scheduler_logger.SchedulerLogger(log_file)
        self.three_core_jobs = ["blackscholes", "vips", "ferret", "freqmine"]

        self.container_info = {
            "blackscholes": {
                "image": "anakli/cca:parsec_blackscholes",
                "cpuset_cpus": "1,2,3",
                "num_threads": 3
            },
            "canneal": {
                "image": "anakli/cca:parsec_canneal",
                "cpuset_cpus": "2,3",
                "num_threads": 2
            },
            "dedup": {
                "image": "anakli/cca:parsec_dedup",
                "cpuset_cpus": "2,3",
                "num_threads": 2
            },
            "ferret": {
                "image": "anakli/cca:parsec_ferret",
                "cpuset_cpus": "1,2,3",
                "num_threads": 3
            },
            "freqmine": {
                "image": "anakli/cca:parsec_freqmine",
                "cpuset_cpus": "1,2,3",
                "num_threads": 3
            },
            "radix": {  # MUST BE ON 2 CORES ONLY, altfel face ca simion
                "image": "anakli/cca:splash2x_radix",
                "cpuset_cpus": "2,3",
                "num_threads": 2
            },
            "vips": {
                "image": "anakli/cca:parsec_vips",
                "cpuset_cpus": "1,2,3",
                "num_threads": 3
            }
        }


    def get_job_from_container_name(self, container_name: str):
        match container_name:
            case "scheduler":
                return scheduler_logger.Job.SCHEDULER
            case "memcached":
                return scheduler_logger.Job.MEMCACHED
            case "blackscholes":
                return scheduler_logger.Job.BLACKSCHOLES
            case "canneal":
                return scheduler_logger.Job.CANNEAL
            case "dedup":
                return scheduler_logger.Job.DEDUP
            case "ferret":
                return scheduler_logger.Job.FERRET
            case "freqmine":
                return scheduler_logger.Job.FREQMINE
            case "radix":
                return scheduler_logger.Job.RADIX
            case "vips":
                return scheduler_logger.Job.VIPS


    def pull_images(self):
        for job_name in self.container_info:
            print(f"pulling image {self.container_info[job_name]['image']}")
            self.docker_client.images.pull(self.container_info[job_name]["image"])


    def _get_main_pid(self, service_name):
        try:
            result = subprocess.run(
                ['systemctl', 'show', '--property', 'MainPID', '--value', service_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return None


    def _set_cpu_affinity(self, pid, cpu_list):
        try:
            subprocess.run(
                ['taskset', '-a', '-p', f'--cpu-list', cpu_list, pid],
                check=True
            )
            print(f"Set CPU affinity of PID {pid} to {cpu_list}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to set CPU affinity: {e}")
            return None


    def expand_memcached_to_2_cores(self):
        pid = self._get_main_pid(MEMCACHED_PROCESS)
        self.memcached_num_cores = 2
        self.logger.update_cores(self.get_job_from_container_name("memcached"), ["0","1"])
        if pid and pid != "0":
            self._set_cpu_affinity(pid, "0-1")
        else:
            print(f"bad pid {pid}")


    def constrain_memcached_to_1_core(self):
        pid = self._get_main_pid(MEMCACHED_PROCESS)
        self.memcached_num_cores = 1
        self.logger.update_cores(self.get_job_from_container_name("memcached"), ["0"])
        if pid and pid != "0":
            self._set_cpu_affinity(pid, "0")
        else:
            print(f"bad pid {pid}")


    def get_containers_on_core(self, core):
        result = list()
        for container in self.docker_client.containers.list(filters={"status": "running"}):
            if str(core) in container.attrs['HostConfig'].get('CpusetCpus', ''):
                result.append(container.name)
        return result


    # should only include running containers
    def get_containers_on_corei_not_corej(self, core1, core2):
        result = list()
        for container in self.docker_client.containers.list(filters={"status": "running"}):
            if str(core1) in container.attrs['HostConfig'].get('CpusetCpus', '') and not str(core2) in container.attrs['HostConfig'].get('CpusetCpus', ''):
                result.append(container.name)
        return result


    # should update self.finished
    def gather_finished_containers(self):
        result = list()
        for container in self.docker_client.containers.list(all=True, filters={"status": "exited"}):
            result.append(container.name)
        self.finished = result


    # should first check for paused jobs on the core
    # should do nothing if everything is scheduled or finished
    def schedule_next_job(self, core: str):
        paused_containers = self.docker_client.containers.list(all=True, filters={"status": "paused"})
        
        for paused_container in paused_containers:
            cpu_info = paused_container.attrs['HostConfig']
            cpuset_cpus = cpu_info.get("CpusetCpus")

            if core in cpuset_cpus:
                paused_container.unpause()
                print(f"unpausing container: {paused_container.name}")
                return
            
        for container in self.docker_client.containers.list(all=True):
            if container.status == "created":
                container.update(cpuset_cpus=core)
                container.start()
                self.logger.job_start(self.get_job_from_container_name(container.name), core.split(","), self.container_info[container.name]["num_threads"])
                print(f"starting container: {container.name}")
                return


    def remove_core(self, container, core):
        cores = self.docker_client.containers.get(container).attrs['HostConfig'].get('CpusetCpus', '').split(",")
        if str(core) in cores:
            cores.remove(str(core))
            self.logger.update_cores(self.get_job_from_container_name(container), cores)
            self.docker_client.containers.get(container).update(cpuset_cpus=",".join(cores))

    def add_core(self, container, core):
        cores = self.docker_client.containers.get(container).attrs['HostConfig'].get('CpusetCpus', '')
        if str(core) not in cores:
            new_cores = f"{cores},{core}"
            self.logger.update_cores(self.get_job_from_container_name(container), new_cores.split(","))
            self.docker_client.containers.get(container).update(cpuset_cpus=f"{new_cores}")


    def get_per_core_cpu_usage(self) -> list:
        cpu_per_core = psutil.cpu_percent(interval=0.5, percpu=True)
        return cpu_per_core
    

    def get_memcached_cpu_usage(self, cpu_per_core) -> float:
        if self.memcached_num_cores == 1:
            return cpu_per_core[0]
        else: # memcached has 2 cores: 0,1
            return cpu_per_core[0] + cpu_per_core[1]

        
    def create_container(self, image: str, job_name: str, cpuset_cpus: str, num_threads: int):
        command = ["./run", "-a", "run", "-S", "parsec", "-p", job_name, "-i", "native", "-n", str(num_threads)]
        if job_name == "radix":
            command[4] = "splash2x"

        try:
            container = self.docker_client.containers.create(
                image,
                command=command,
                name=job_name,
                cpuset_cpus=cpuset_cpus,
                detach=True
            )
            print("Container created, name:", container.name)
        except docker.errors.APIError as e:
            print("Docker error:", e.explanation)


    def create_all_containers(self):
        for job_name in self.container_info.keys():
            self.create_container(
                self.container_info[job_name]["image"],
                job_name,
                self.container_info[job_name]["cpuset_cpus"],
                self.container_info[job_name]["num_threads"]
            )
    

    def update_container(self, job_name: str, cpuset_cpus: str):
        self.docker_client.containers.get(job_name).update(cpuset_cpus=cpuset_cpus)


    def pause_container(self, job_name: str):
        print(f"pausing container: {job_name}")
        self.logger.job_pause(self.get_job_from_container_name(job_name))
        self.docker_client.containers.get(job_name).pause()


    def pause_containers(self, containers: list[str]):
        for container_name in containers:
            self.pause_container(container_name)

    
    def unpause_container(self, job_name: str):
        self.logger.job_unpause(self.get_job_from_container_name(job_name))
        self.docker_client.containers.get(job_name).unpause()


    def basic_sequential_schedule_with_memcached(self):
        self.pull_images()
        start_time = time.time()
        self.create_all_containers()

        for job_name in self.container_info:
            container = self.docker_client.containers.get(job_name)
            container.start()
            self.logger.job_start(self.get_job_from_container_name(job_name),
                                  self.container_info[job_name]["cpuset_cpus"].split(","),
                                  self.container_info[job_name]["num_threads"])

            print(f"started container for job: {job_name}")

            is_running = True
            while is_running:
                status = self.docker_client.containers.get(job_name).status
                if status == "exited":
                    is_running = False
                    print(f"job {job_name} finished")
                    self.logger.job_end(self.get_job_from_container_name(job_name))
                else:
                    if job_name in self.three_core_jobs:
                        cpu_per_core = self.get_per_core_cpu_usage()
                        memcached_cpu = self.get_memcached_cpu_usage(cpu_per_core)
                        self.logger.log_cpu_utilisation(self.get_job_from_container_name("memcached"), cpu_per_core)
                        if self.memcached_num_cores == 1:
                            if memcached_cpu > 40:
                                self.expand_memcached_to_2_cores()
                        else:
                            if memcached_cpu < 80:
                                self.constrain_memcached_to_1_core()
                                self.add_core(job_name, "1")
                            elif memcached_cpu <= 140:
                                self.add_core(job_name, "1")
                            elif memcached_cpu > 140:
                                self.remove_core(job_name, "1")
                    else:
                        time.sleep(1)

        end_time = time.time()
        print(f"took {end_time - start_time} seconds")
        self.logger.end()
        time.sleep(60)



def main():
    log_file = sys.argv[1]
    c = Controller(log_file)
    c.basic_sequential_schedule_with_memcached()


if __name__ == "__main__":
    print("entering main controller...")
    main()
    print("exited main controller..")
