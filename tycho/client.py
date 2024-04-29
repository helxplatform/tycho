import requests
import ipaddress
import json
import logging
import os
import git
import shutil
import sys
import traceback
import argparse
import yaml
from tycho.tycho_utils import TemplateUtils
from tycho.config import Config
from tycho.exceptions import TychoException
from tycho.actions import StartSystemResource, StatusSystemResource, DeleteSystemResource, ModifySystemResource
from kubernetes import client as k8s_client, config as k8s_config

logger = logging.getLogger (__name__)

mem_converter = {
    'M' : lambda v : v * 10 ** 6,
    'G' : lambda v : v * 10 ** 9,
    'T' : lambda v : v * 10 ** 12,
    'P' : lambda v : v * 10 ** 15,
    'E' : lambda v : v * 10 ** 18
}



class TychoService:
    """ Represent a service endpoint. """
    try_minikube = True

    def __init__(self, name, app_id, ip_address, port, sid=None, creation_time=None, username="",utilization={}, conn_string="", workspace_name="",is_ready=False):
        self.name = name
        self.app_id = app_id
        self.ip_address = ip_address
        self.port = port
        self.identifier = sid
        self.creation_time = creation_time
        self.username = username
        self.utilization = utilization
        self.total_util = self.get_utilization (utilization)
        self.conn_string = conn_string
        self.workspace_name = workspace_name
        self.is_ready = is_ready
            
    def get_utilization (self, utilization):
        total = {
            "gpu": 0,
            "cpu" : 0,
            "memory" : 0,
            "ephemeralStorage" : 0
        }
        for key, val in utilization.items ():
            if 'cpu' in val.keys():
                if 'm' in val['cpu']:
                    total['cpu'] = total['cpu'] + int(val['cpu'].replace ('m', ''))
                else:
                    total['cpu'] = total['cpu'] + int(val['cpu']) * 1000
            # Will have to adjust this if we want to check for non-nvidia GPUs.
            for key in val.keys():
                if 'nvidia' in key:
                    total['gpu'] = total['gpu'] + int(val[key]) * 1000
            mem = val['memory'].replace ("i", "")
            """ Run the conversion function designated by the last character of the value on the integer value """
            mem_val = mem_converter[mem[-1]] (int(mem[:-1]))
            total['memory'] = total['memory'] + mem_val
        total['memory'] = f"{total['memory'] / (10 ** 9)}"
        return total

    def __repr__(self):
        b = f"id: {self.identifier} time: {self.creation_time} util: {self.utilization}"
        return f"name: {self.name} ip: {self.ip_address} port: {self.port} user:{self.username} {b}"


class TychoStatus:
    """ A response from a status request. """ 
    def __init__(self, status, result, message):
        self.status = status
        self.services = list(map(lambda v: TychoService (**v), result))
        self.message = message

    def __repr__(self):
        return f"status: {self.status} svcs: {[ str(s) for s in self.services ]} msg: {self.message}"


class TychoSystem:
    """ Represents a running system. """
    def __init__(self, status, result, message):
        self.status = status
        if status == 'error':
            raise TychoException (f"status:{status} result:{result} message:{message}")
        self.name = result['name']
        self.identifier = result['sid']
        self.services = [
            TychoService(name=k, app_id=result['name'], ip_address=v['ip_address'], port=v['port-1'])
            for k, v in result['containers'].items ()
        ]
        self.conn_string = result['conn_string']
        self.message = message

        
class TychoClient:
    """ Python client to Tycho dynamic application deployment API. """

    def __init__(self, url="http://localhost:5000"):
        """ Construct a client.

            :param url: URL of the Tycho API endpoint.
            :type url: string
        """
        self.url = f"{url}/system"
        self.actions = {
            'start': StartSystemResource(),
            'status': StatusSystemResource(),
            'delete': DeleteSystemResource(),
            'modify': ModifySystemResource()
        }
        
    def request (self, service, request):
        """ Send a request to the server. Generic underlayer to all requests. 

            :param service: URL path to the service to invoke.
            :param request: JSON to send to the API endpoint.
        """
        if os.environ.get("REST_API", "false") == "true":
            response = requests.post (f"{self.url}/{service}", json=request) #nosec B113
            result_text = f"HTTP status {response.status_code} received from service: {service}"
            logger.debug (f"TychoClient.request - {result_text}")
            if not response.status_code == 200:
                raise Exception (f"Error: {result_text}")
            result = response.json ()
            logger.debug (f"TychoClient.request - {json.dumps(result, indent=2)}")
        else:
            result = self.actions.get(service).post(request)
            logger.debug(f"TychoClient.request -  {result} received from service: {service}")
        return result
    
    def format_name (self, name):
        """ Format a service name to be a valid DNS label.
        
            :param name: Format a name.
        """
        return name.replace (os.sep, '-')

    def parse_env (self, environment):
        return {
            line.split("=", maxsplit=1)[0] : line.split("=", maxsplit=1)[1]
            for line in environment.split ("\n") if '=' in line
        }
        
    def start (self, request):
        """ Start a service. 
        
            The general format of a start request is::

                {
                   "name"   : <name of the system>,
                   "env"    : <JSON dict created from .env environment variables>,
                   "system" : <JSON of a docker-compose yaml>
                } 

            :param request: A request object formatted as above.
            :type request: JSON
            :returns: Returns a TychoSystem object
        """
        response = self.request ("start", request)
        error = response.get('result',{}).get('error',None)
        if error == 'error':
            for e in error:
                logger.error (e)
        return TychoSystem (**response)

    def delete (self, request):
        """ Delete a service. 
            
            Given the GUID of a running service, delete it and all its constituent parts.

            The general format of a delete request is::
        
                {
                   "name" : <GUID>
                }

            :param request: A request formatted as above.
            :type request: JSON
        """
        logger.error (f"-- delete: {json.dumps(request, indent=2)}")
        print (f"-- delete: {json.dumps(request, indent=2)}")
        return self.request ("delete", request)
    
    def status (self, request): 
        """ Get status of running systems.
        
            Get the status of a system by GUID or across systems.

            The format of a request is::
 
                {}

            :param request: Request formatted as above.
            :type request: JSON
        """
        response = self.request ("status", request)
        return TychoStatus (**response)

    def modify(self, request):
        """ Takes in a JSON formatted metadata and specs of a running system.

            Some examples for a request,
            * {"tycho-guid": <guid>, "labels": {"name": <any-name>}, "resources": {"cpu": <cpu>, "memory": <memory>}}
            * {"tycho-guid": <guid>, "labels": {"name": "<any-name>"}}
            * {"tycho-guid": <guid>, "resources": {"cpu": <cpu>, "memory": <memory>}}

            :param request: Request formatted as above
            :type request: json

            :returns: A list of all the patches applied to the system
            :rtype: A list
        """
        response = self.request("modify", request)
        return response

    def up (self, name, system, settings=""):
        """ Bring a service up starting with a docker-compose spec. 
        
            CLI endpoint to start a service on the Tycho compute fabric.::

                tycho up -f path/to/docker-compose.yaml

            :param name: Name of the system.
            :type name: str
            :param system: Docker-compose JSON structure.
            :type system: JSON
            :param settings: The textual contents of a .env file.
            :type settings: str
        """
        services = {}
        for container_name, container in system['services'].items ():
            if 'ports' in container.keys():
                ports = container['ports']
                for port in ports:
                    port_num = int(port.split(':')[1] if ':' in port else port)
                    services[container_name] = {
                        "port" : port_num
                        #"clients" : [ "192.16.1.179" ]
                    }
                    
        request = {
            "name"   : self.format_name (name),
            "principal" : '{"username": "renci"}',
            "serviceaccount" : "default",
            "env"    : self.parse_env (settings),
            "system" : system,
            "services" : services
        }
        logger.debug (f"client.up - request: {json.dumps(request, indent=2)}")
        response = self.start (request)
        logger.debug (f"client.up - response: {response}")
        if response.status == 'error':
            print (response.message)
        else:
            format_string = '{:<30} {:<35} {:<15} {:<7}'
            print (format_string.format("SERVICE", "GUID", "IP_ADDRESS", "PORT"))
            for service in response.services:
                print (format_string.format (
                    TemplateUtils.trunc (service.name, max_len=28),
                    TemplateUtils.trunc (response.identifier, max_len=33),
                    service.ip_address,
                    service.port))
                break

    def list (self, name, terse=False):
        """ List status of executing systems.

            CLI endpoint to list status of services.::

                tycho status
                tycho status -terse

            :param name: GUID of a service to get status for.
            :type name: str
            :param terse: Print just the GUID for running systems
            :type terse: boolean
        """
        try:
            request = { "name" : self.format_name (name) } if name else {}
            request['username'] = 'renci'
            response = self.status (request)
            logger.debug (f"client.list - response: {response}")
            if response.status  == 'success':
                if terse:
                    for service in response.services:
                        print (service.identifier)
                elif len(response.services) == 0:
                    print ('None running')
                else:
                    format_string = '{:<30} {:<35} {:<15} {:<7} {:<1}'
                    print (format_string.format("SYSTEM", "GUID", "IP_ADDRESS", "PORT", "CREATION_TIME"))
                    for service in response.services:
                        print (format_string.format (
                            TemplateUtils.trunc (service.name, max_len=28),
                            TemplateUtils.trunc (service.identifier, max_len=33),
                            service.ip_address,
                            service.port,
                            service.creation_time))
            elif response.status == 'error':
                print (response)
        except Exception as e:
            raise e
        
    def down (self, names):
        """ Bring down a service. 

            CLI endpoint for deleting running systems.::

                tycho down <GUID>

            :param names: GUIDs of systems to delete.
            :type name: str
        """
        try:
            for name in names:
                response = self.delete ({ "name" : self.format_name(name) })
                logger.debug (f"TychoClient.down - {json.dumps(response,indent=2)}")
                if response.get('status',None) == 'success':
                    print (f"{name}")
                else:
                    print (json.dumps (response, indent=2))
        except Exception as e:
            traceback.print_exc()

    def patch(self, mod_items):
        """
            Modify a running system.
            Takes in a JSON formatted metadata and specs of a running system.

            Some examples for a request,
            * {"tycho-guid": <guid>, "labels": {"name": <any-name>}, "resources": {"cpu": <cpu>, "memory": <memory>}}
            * {"tycho-guid": <guid>, "labels": {"name": "<any-name>"}}
            * {"tycho-guid": <guid>, "resources": {"cpu": <cpu>, "memory": <memory>}}

            CLI endpoint for modifying running systems::
                python client -m <JSON object>

            :param mod_items: Request formatted as above
            :type mod_items: json

            :returns: A list of all the patches applied to the system
            :rtype: A list
        """
        logger.info(f"System specifications and metadata to be modified: {mod_items}")
        try:
            response = self.modify(mod_items)
            logger.debug(f"TychoClient.patch - {json.dumps(response, indent=2)}")
            return response
        except (AttributeError, Exception) as e:
            logger.exception(f"Error in modifying system. {e}")

            
class TychoClientFactory:
    """ Locate a Tycho API instance in a Kubernetes cluster.

        This is written to work wheter run in-cluster or standalone. If we're running outside of 
        the cluster we use the environment's kubernetes configuration. If we're running 
        insde kubernetes, we use the "in cluster" configuration to locate the configuration.        
    """
    def __init__(self):
        """ Initialize connection to Kubernetes.

            Load the kubernetes configuration in an enviroment appropriate way as described above.

            Then create the K8S API endpoint.
        """
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            logger.debug ("--loading in cluster configuration.")
            k8s_config.load_incluster_config()
        else:
            logger.debug ("--loading kube config, cluster external.")
            k8s_config.load_kube_config()
        api_client = k8s_client.ApiClient()
        self.api = k8s_client.CoreV1Api(api_client)
        
    def get_client (self, name="tycho-api", namespace="default", default_url="http://localhost:5000"):
        """ Locate the client endpoint using the K8s API.

            Locate the Tycho API using the K8S API. We do this by reading services in the
            given namespace with the given name. Then we look for a load balancer IP and port 
            to build a URL. This works for public cloud clusters. With some modification, it
            could work for Minikube but that is a future effort.

            :param name: Name of the Tycho API service in Kubernetes.
            :type name: str
            :param namespace: The namespace the service is deployed to.
            :type namespace: str
        """
        try:
           with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as secrets:
               for line in secrets:
                   namespace = line
                   raise Exception
        except Exception as e:
            logger.warning(f"cannot get namespace from file: {e}")

        url = None
        client = None
        try:
            service = self.api.read_namespaced_service(
                name=name,
                namespace=namespace)
            if not service:
                url = default_url
            elif service.status and service.status.load_balancer:
                ip_address = "tycho-api"
                port = service.spec.ports[0].port
                logger.debug (f"located tycho api instance in kube")
                url = f"http://{ip_address}:{port}"
            elif service.spec and len(service.spec.ports) > 0:
                logger.debug ("--looking in minikube for a node port based service.")
                ip = os.popen('minikube ip').read().strip ()
                if len(ip) > 0:
                    try:
                        ipaddress.ip_address (ip)
                        logger.info (f"configuring minikube ip: {ip}")
                        port = service.spec.ports[0].node_port
                        logger.debug (f"located tycho api instance in minikube")
                        url = f"http://{ip}:{port}"
                    except ValueError as e:
                        logger.error ("unable to get minikube ip address")
                        traceback.print_exc()
            print(f"URL: {url}")
        except Exception as e:
            url = default_url
            print(f"url: {url}")
            logger.info (f"cannot find {name} in namespace {namespace}")

        logger.info (f"creating tycho client with url: {url}")
        return TychoClient (url=url)


class TychoApps:
    def __init__(self, app):
        self.app = app
        self.repo_url = 'https://github.com/heliumplusdatastage/app-support-prototype.git'
        self.repo_name = 'app-support-prototype'
        self.apps_dir = 'dockstore-yaml-proposals'
        self.source_file = 'docker-compose.yaml'
        self.env = '.env'
        self.metadata = {}

    def deleterepo(self, repo_path):
        shutil.rmtree(repo_path)

    def getmetadata(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            git.Git(base_dir).clone(self.repo_url)
        except Exception as e:
            traceback.print_exc(e)
        repo_path = os.path.join(base_dir, self.repo_name)
        apps_path = os.path.join(repo_path, self.apps_dir)
        for _, dnames, _ in os.walk(apps_path):
            if self.app in dnames:
                system_path = os.path.join(apps_path, self.app, self.source_file)
                env_path = os.path.join(apps_path, self.app, self.env)
                with open(system_path, "r") as stream:
                    system = yaml.safe_load(stream)
                    self.metadata['System'] = system
                if os.path.exists(env_path):
                    with open(env_path, 'r') as stream:
                        settings = stream.read()
                        self.metadata['Settings'] = settings
            break
        self.deleterepo(repo_path)
        return self.metadata


if __name__ == "__main__":
    """ A CLI for Tycho. """
    status_command="@status_command"
    parser = argparse.ArgumentParser(description='Tycho Client')
    parser.add_argument('-u', '--up', help="Launch service.", action='store_true')
    parser.add_argument('-s', '--status', help="Get status of running systems.", nargs='?', const=status_command, default=None)
    parser.add_argument('-d', '--down', help="Delete a running system. Requires a system id.", nargs='*')
    parser.add_argument('-p', '--port', type=int, help="Port to expose.")
    parser.add_argument('-c', '--container', help="Container to run.")
    parser.add_argument('-n', '--name', help="Service name.")
    parser.add_argument('--service', help="Tycho API URL.", default="http://localhost:5000")
    parser.add_argument('--env', help="Env variable", default=None)
    parser.add_argument('--command', help="Container command", default=None)
    parser.add_argument('--settings', help="Environment settings", default=None)
    parser.add_argument('-f', '--file', help="A docker compose (subset) formatted system spec.")
    parser.add_argument('-a', '--app', help="Name of the app. Should be one of the apps available in app-support-prototype repo")
    parser.add_argument('-t', '--trace', help="Trace (debug) logging", action='store_true', default=False)
    parser.add_argument('--terse', help="Keep status short", action='store_true', default=False)
    parser.add_argument('-v', '--volumes', help="Mounts a volume", default=None)
    parser.add_argument('-m', '--modify', help="Modify a running system", default=None)
    args = parser.parse_args ()
                
    """ Honor debug and trace settings. """
    if args.trace:
        logging.basicConfig(level=logging.DEBUG)

    """ Resolve environment settings file as text. """
    settings=""
    if args.settings:
        with open(args.settings, "r") as stream:
            settings = stream.read ()

    name=args.name
    system=None
    if args.app:
        """Name for the app"""
        name = args.app

        """ Apply settings. """
        tychoapps = TychoApps(args.app)
        metadata = tychoapps.getmetadata()

        if 'System' in metadata.keys():
            system = metadata['System']
        if 'Settings' in metadata.keys():
            settings = metadata['Settings']
            print(f"settings: {settings}")

    elif args.file:
        if not args.name:
            """ We've been given a docker-compose.yaml. Come up with a name for the app 
            based on the containing directory if none has been otherwise supplied. """
            if os.sep in args.file:
                args.file = os.path.abspath (args.file)
                name = args.file.split('.')[0] if '.' in args.file else args.file
                name = name.split (os.sep)[-2]
            else:
                name = os.path.basename (os.getcwd ())

        """ Apply settings. """
        env_file = os.path.join (os.path.dirname (args.file), ".env")
        if os.path.exists (env_file):
            with open (env_file, 'r') as stream:
                settings = stream.read ()
                # added safeloader here, per bandit instructions.
        with open(args.file, "r") as stream:
            system = yaml.load (stream.read (), Loader=yaml.SafeLoader)
    else:
        """ Generate a docker-compose spec based on the CLI args. """
        name = args.name
        template_utils = TemplateUtils (config=Config())
        template = """
          version: "3"
          services:
            {{args.name}}:
              image: {{args.container}}
              {% if args.command %}
              entrypoint: {{args.command}}
              {% endif %}
              {% if args.port %}
              ports:
                - "{{args.port}}"
              {% endif %}
              {% if args.volumes %}
              volumes:
                - "{{args.volumes}}"
              {% endif %}"""

        system = template_utils.render_text(
            TemplateUtils.apply_environment (settings, template),
            context={ "args" : args })

    client = None
    """ Locate the Tycho API endpoint. Instantiate a client to use the endpoint. """
    if args.service == parser.get_default ("service"):
        """ If the endpoint is the default value, try to discover the endpoint in kube. """
        client_factory = TychoClientFactory ()
        client = client_factory.get_client ()
        if not client:
            """ That didn't work so use the default value. """
            client = TychoClient (url=args.service)
    if not client:
        logger.info (f"creating client directly {args.service}")
        client = TychoClient (url=args.service)

    if args.up:
        client.up (name=name, system=system, settings=settings)
    elif args.down:
        client.down (names=args.down)
    elif args.status:
        if args.status == status_command: # non arg
            client.list (name=None, terse=args.terse)
        else:
            client.list (name=args.status, terse=args.terse)
    elif args.modify:
        mod_items = json.loads(args.modify)
        client.patch(mod_items=mod_items)
