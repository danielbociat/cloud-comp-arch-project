import docker
import psutil
import time

class Controller:
    def __init__(self):
        self.docker_client = docker.from_env()
        self.finished = list()
        self.memcached_single_core = True
        # TODO add thresholds
        self.T1_qps = 0
        self.T2_qps = 0
        self.T1_cpu = 0
        self.T2_cpu = 0
        self.container_info = {
            "blackscholes": {
                "image": "anakli/cca:parsec_blackscholes",
                "obj": None,
                "cpuset_cpus": "0",
                "num_threads": 2
            },
            "canneal": {
                "image": "anakli/cca:parsec_canneal",
                "obj": None,
                "cpuset_cpus": "0",
                "num_threads": 2                
            },
            "dedup": {
                "image": "anakli/cca:parsec_dedup",
                "obj": None,
                "cpuset_cpus": "0",
                "num_threads": 2
            },
            "ferret": {
                "image": "anakli/cca:parsec_ferret",
                "obj": None,
                "cpuset_cpus": "0",
                "num_threads": 2                
            },
            "freqmine": {
                "image": "anakli/cca:parsec_freqmine",
                "obj": None,
                "cpuset_cpus": "0",
                "num_threads": 2
            },
            "radix": {
                "image": "anakli/cca:splash2x_radix",
                "obj": None,
                "cpuset_cpus": "0",
                "num_threads": 2
            },
            "vips": {
                "image": "anakli/cca:parsec_vips",
                "obj": None,
                "cpuset_cpus": "0",
                "num_threads": 2                
            }
        }

    #TODO implement
    def get_latest_p95_latency(self):
        return 0.5
    def expand_memcached_to_2_cores(self):
        pass
    def constrain_memcached_to_1_core(self):
        pass
    def get_containers_on_core(self, core):
        return list()

    # should only include running containers
    def get_containers_on_corei_not_corej(self, core1, core2):
        return list()

    # should update self.finished
    def gather_finished_container(self):
        pass

    # should first check for pause jobs on the core
    # should do nothing if everything is scheduled or finished
    def schedule_next_job(self, core):
        pass

    def add_core(self, container, core):
        pass



    def get_memcached_resource_usage(self) -> dict:
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                if "memcached" in info["name"]:
                    return info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return {}

    
    def start_container(self, image: str, job_name: str, cpuset_cpus: str, num_threads: int):
        try:
            container = self.docker_client.containers.run(
                image,
                command=["./run", "-a", "run", "-S", "parsec", "-p", job_name, "-i", "native", "-n", str(num_threads)],
                name=job_name,
                cpuset_cpus=cpuset_cpus,
                detach=True,
                remove=True
            )
            print("Container started, ID:", container.id)
            self.container_info[job_name]["obj"] = container
        except docker.errors.APIError as e:
            print("Docker error:", e.explanation)

    
    def update_container(self, job_name: str, cpuset_cpus: str):
        self.container_info[job_name]["obj"].update(cpuset_cpus=cpuset_cpus)

    
    def pause_container(self, job_name: str):
        self.container_info[job_name]["obj"].pause()

    
    def unpause_container(self, job_name: str):
        self.container_info[job_name]["obj"].unpause()        


    def schedule(self):
        # start jobs

        # for job_name in self.container_info.keys():
        #     self.start_container(
        #         self.container_info[job_name]["image"],
        #         job_name,
        #         self.container_info[job_name]["cpuset_cpus"],
        #         self.container_info[job_name]["num_threads"]
        #     )


        while len(self.finished) < 7:
            memcached_latency = self.get_latest_p95_latency()

            if memcached_latency < self.T1_qps: #small latency, 1 core works
                self.constrain_memcached_to_1_core()
            elif memcached_latency < self.T2_qps: #medium latency, use 2 cores for safety
                self.expand_memcached_to_2_cores()
            else:   # high latency, use 2 cores and pause everything on the second core
                self.expand_memcached_to_2_cores()
                containers_core_1 = self.get_containers_on_core(1)
                for container in containers_core_1:
                    self.pause_container(container)

            cpu_utilisation = self.get_memcached_resource_usage() # assume it works per core
            if cpu_utilisation[2] < self.T1_cpu: # low utilisation on core 2, schedule more
                self.schedule_next_job(2)
            elif cpu_utilisation[2] < self.T2_cpu: # medium utilisation, go to core 3
                if cpu_utilisation[3] < self.T1_cpu:
                    self.schedule_next_job(2)
                elif cpu_utilisation[3] < self.T2_cpu:
                    pass # shoudl maybe schedule sth on 1?
                else: # need to move to 1
                    if cpu_utilisation[1] < self.T1_cpu:
                        conts = self.get_containers_on_corei_not_corej(3, 1)
                        if len(conts) != 0:
                            self.add_core(conts[0], 1)
                        else:
                            containers3 = self.get_containers_on_core(3)
                            self.pause_container(containers3)
                    else:
                        containers3 = self.get_containers_on_core(3)
                        self.pause_container(containers3)

            else: # high utilisation, add other cores for containers or pause something
                if cpu_utilisation[3] < self.T1_cpu: #add core 3 for some container running on core 2
                    conts = self.get_containers_on_corei_not_corej(2, 3)
                    if len(conts) != 0:
                        self.add_core(conts[0], 3)
                elif cpu_utilisation[3] < self.T2_cpu: # 3 has a balanced utilisation, try to move on 1
                    if cpu_utilisation[1] < self.T1_cpu:
                        conts = self.get_containers_on_corei_not_corej(2, 1)
                        if len(conts) != 0:
                            self.add_core(conts[0], 1)
                        else:
                            containers2 = self.get_containers_on_core(2)
                            self.pause_container(containers2)
                    else:
                        containers2 = self.get_containers_on_core(2)
                        self.pause_container(containers2)
                else: # both 2 and 3 have high utilisation
                    containers1 = self.get_containers_on_core(1)
                    containers2 = self.get_containers_on_core(2)
                    containers3 = self.get_containers_on_core(3)
                    containers23 = [c for c in containers2 if c in containers3]
                    # try to move sth on 1
                    if cpu_utilisation[1] < self.T1_cpu:
                        # prioritise moving containers that are shared by 2 and 3
                        movable_conts = [c for c in containers23 if c not in containers1]
                        if len(movable_conts) > 0:
                                self.add_core(movable_conts[0], 1)
                        # if nothing shared can be moved to 1, move sth from c2, stop sth on c3
                        else:
                            self.add_core(containers2, 1)
                            self.pause_container(containers3)
                    else: # can't move to 1
                        if len(containers23) != 0:
                            self.pause_container(containers23[0])
                        else:
                            self.pause_container(containers2[0])
                            self.pause_container(containers3[0])


            self.gather_finished_containers()
        print("done looping")
        time.sleep(60)



def main():
    c = Controller()
    c.schedule()


if __name__ == "__main__":
    print("entering main controller...")
    main()
    print("exited main controller..")
