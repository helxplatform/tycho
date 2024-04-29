import json
import logging
import os
import random
import shutil
import glob
import subprocess
import sys
import threading
import traceback
import yaml
from tycho.compute import Compute
from tycho.model import System
from tycho.tycho_utils import TemplateUtils
from tycho.exceptions import DeleteException
from tycho.exceptions import StartException
from compose.cli.main import TopLevelCommand, project_from_options

logger = logging.getLogger (__name__)

class DockerComposeThread(threading.Thread):
    """ Run Docker-Compose in a thread and communicate via subprocess. """

    def __init__(self, system, port, configured, app_root):
        """ Invoke thread init and connect the system. """
        threading.Thread.__init__(self)
        self.system = system
        self.port = port
        self.container_map = {}
        self.configured = configured
        self.app_root = app_root
        
    def run (self):
        """ Execute the system. """
        logger.debug (f"creating compose app: {self.system.identifier}")
        os.makedirs (self.app_root)
        #docker_compose_file = os.path.join (self.app_root, f"docker-compose.yaml")
        docker_compose_file = os.path.join (self.app_root, f"{self.system.name}.yaml")
        env_file = os.path.join (self.app_root, ".env")

        """ For now, write literal input text. TODO, generate to incoporate policy. """
        with open (docker_compose_file, 'w') as stream:
            stream.write (self.system.source_text)
        env = f"""HOST_PORT={self.port}\nLOCAL_STORE=./\n"""
        print (f"--env----------> {env}")
        with open (env_file, 'w') as stream:
            stream.write (env)

        """ Find and return ports for each container. """
        config = yaml.safe_load (TemplateUtils.apply_environment (
            env,
            self.system.source_text))
        logger.debug (f"Building conainer map for system {self.system.name}")
        for c_name, c_config in config.get ('services', {}).items ():
            print (f"--cname:{c_name} c_config:{c_config}")
            self.container_map[c_name] = {
                f"{c_name}-{i}" : port.split(':')[0] if ':' in port else port
                for i, port in enumerate(c_config.get('ports', []))
            }
            print (f"-- container map {self.container_map}")

        self.configured.set ()
        
        # Run docker-compose in the directory.
        logger.debug (f"Garbage collecting unused docker networks...")
        p = subprocess.Popen(
            [ "docker", "network", "prune", "--force" ],
            stdout=subprocess.PIPE,
            cwd=self.app_root)

        logger.debug (f"Running system {self.system.name} in docker-compose")
        command = f"docker-compose --project-name {self.system.name} -f {self.system.name}.yaml up --detach"
        print (command)
        p = subprocess.Popen(
            command.split (),
            stdout=subprocess.PIPE,
            cwd=self.app_root)
        
class DockerComposeCompute(Compute):
    def __init__(self, config):
        self.config = config
        self.app_root_base = "apps"
    def start (self, system, namespace="default"):
        import subprocess
        """ Generate a globally unique identifier for the application. All associated 
        objects will share this identifier. """

        app_root = os.path.join (self.app_root_base, system.identifier)
        
        """ Generate a unique port for the system. Needs to be generalized to multi-container 
        while somehow preserving locally meaningful port names."""
        port = random.randint (30000, 40000)
        configured = threading.Event()
        docker_compose_thread = DockerComposeThread (system, port, configured, app_root)
        docker_compose_thread.start ()
        """ Wait for the thread to configure the app to run.
        If this takes longer than five seconds, the thread has probably errored. Continue. """
        configured.wait (5) 
        return {
            'name' : system.name,
            'sid' : system.identifier,
            'containers' : docker_compose_thread.container_map
        }

    def status (self, name, namespace="default"):
        """ Report status of running systems. """
        print (os.getcwd ())
        apps = [ guid for guid in os.listdir(self.app_root_base)
                 if os.path.isdir(os.path.join(self.app_root_base, guid)) ]
        result = []
        cur_dir = os.getcwd ()
        for app in apps:
            app_root = os.path.join (self.app_root_base, app)

            command = f"docker-compose --project-name {app} ps".split ()
            logger.debug (f"--command: {command}")
            p = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                cwd=app_root)

            p.stdout.readline ()
            for line in p.stdout:
                print (line)

            result.append ({
                "name" : "--",
                "sid"  : app,
                #"ip"   : None, #"--", #ip_address,
                "port" : "--"
            })
        return result

    def delete (self, name, namespace="default"):
        """ Delete the running process and persistent artifacts. """
        app_root = os.path.join (self.app_root_base, name)

        pattern = os.path.join (app_root, f"*{name}*.yaml")
        print (pattern)
        docker_compose_file = glob.glob (pattern)
        print (docker_compose_file)
        docker_compose_file = os.path.basename (docker_compose_file[0])
        project_name = docker_compose_file.replace (".yaml", "")
        print (f"--project name: {project_name}")
        
        command = f"docker-compose --project-name {project_name} -f {docker_compose_file} down".split ()
        """ Wait for shutdown to complete. """
        p = subprocess.check_call(
            command,
            stdout=subprocess.PIPE,
            cwd=app_root)
        
        """ Delete the app subtree. """
        shutil.rmtree (app_root)
