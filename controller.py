import docker
import psutil
import time

class Controller:
    def __init__(self):
        self.docker_client = docker.from_env()
        self.finished = list()
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
        for i in range(100):
            print(i)
        for job_name in self.container_info.keys():
            self.start_container(
                self.container_info[job_name]["image"],
                job_name,
                self.container_info[job_name]["cpuset_cpus"],
                self.container_info[job_name]["num_threads"]
            )
        for i in range(101, 200):
            print(i)

        # scheduling loop
        usage = self.get_memcached_resource_usage()
        while True:
            time.sleep(1)
            print("looping")
        print("done looping")



def main():
    c = Controller()
    c.schedule()


if __name__ == "__main__":
    print("entering main controller...")
    main()
    print("exited main controller..")
