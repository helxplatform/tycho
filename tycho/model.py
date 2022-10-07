import argparse
import logging
import ipaddress
import json
import os
from typing import OrderedDict, Dict, Any
import uuid
import yaml
import traceback
from tycho.tycho_utils import TemplateUtils

logger = logging.getLogger (__name__)


class Limits:
    """ Abstraction of resource limits on a container in a system. """
    def __init__(self,
                 cpus=None,
                 gpus=None,
                 memory=None):
        """ Create limits.
            
            :param cpus: Number of CPUs. May be a fraction.
            :type cpus: str
            :param gpus: Number of GPUs. May be a fraction.
            :type gpus: str
            :param memory: Amount of memory 
            :type memory: str
        """
        self.cpus = cpus
        self.gpus = gpus
        #assert (self.gpus).is_integer, "Fractional GPUs not supported"
        self.memory = memory
    def __repr__(self):
        return f"cpus:{self.cpus} gpus:{self.gpus} mem:{self.memory}"


class Volumes:
    def __init__(self, id, containers):
        self.id = id
        self.containers = containers
        self.volumes = []
        self.pvcs = []

    def volume(self, container_name, pvc_name, volume_name, path=None, subpath=None):
        self.volumes.append({"container_name": container_name, "pvc_name": pvc_name, "volume_name": volume_name, "path": path, "subpath": subpath})

    def process_volumes(self):
       for index, container in enumerate(self.containers):
           for index, volume in enumerate(container["volumes"]):
               parts = volume.split(":")
               if parts[0] == "pvc":
                   volume_name = parts[1].split("/")[2:3][0]
                   pvc_name = volume_name if volume_name not in self.pvcs else None
                   self.pvcs.append(volume_name)
                   path = parts[2] if len(parts) == 3 else None
                   subpath = "/".join(parts[1].split("/")[3:]) if len(parts) == 3 else None
                   self.volume(container['name'], pvc_name, volume_name, path, subpath)
               else:
                   logger.debug(f"Volume definition should follow the pattern: pvc://<pvc_name>/<sub-path>:<container-path> or pvc://<sub-path>:<container-path>")
                   raise Exception(f"Wrong Volume definition in Container:{container['name']} and Volume:{volume}")
       return self.volumes

class Probe:
    def __init__(self,cmd=None,delay=None,period=None,threshold=None):
        self.cmd = cmd
        self.delay = delay
        self.period = period
        self.threshold = threshold

class HttpProbe(Probe):
    def __init__(self,delay=None,period=None,threshold=None,httpGet=None):
        Probe.__init__(self,None,delay,period,threshold)
        if httpGet != None:
           self.path = httpGet.get("path","/")
           self.port = httpGet.get("port",80)
           self.httpHeaders = httpGet.get("httpHeaders",None)

class TcpProbe(Probe):
    def __init__(self,delay=None,period=None,threshold=None,tcpSocket=None):
        Probe.__init__(self,None,delay,period,threshold)
        if tcpSocket != None:
           self.port = tcpSocket.get("port",None)

class Container:
    """ Invocation of an image in a specific infastructural context. """
    def __init__(self,
                 name,
                 image,
                 command=None,
                 env=None,
                 identity=None,
                 limits=None,
                 requests=None,
                 ports=[],
                 expose=[],
                 depends_on=None,
                 volumes=None,
                 liveness_probe=None,
                 readiness_probe=None):
        """ Construct a container.
        
            :param name: Name the running container will be given.
            :param image: Name of the image to use.
            :param command: Text of the command to run.
            :param env: Environment settings
            :type env: dict
            :param identity: UID of the user to run as.
            :type identity: int
            :param limits: Resource limits
            :type limits: dict
            :param requests: Resource requests
            :type limits: dict
            :param ports: Container ports to expose.
            :type ports: list of int
            :param volumes: List of volume mounts <host_path>:<container_path>
            :type volumes: list of str
            :param securityContext: Contains container security context, runAsUser and fsGroup
            :type securityContext: dict
        """
        self.name = name
        self.image = image
        self.identity = identity
        self.limits = Limits(**limits) if isinstance(limits, dict) else limits
        self.requests = Limits(**requests) if isinstance(requests, dict) else requests
        if isinstance(self.limits, list):
            self.limits = self.limits[0] # TODO - not sure why this is a list.
        self.ports = ports
        self.expose = expose
        self.depends_on = depends_on
        self.command = command
        self.env = \
                   list(map(lambda v : list(map(lambda r: str(r), v.split('='))), env)) \
                   if env else []
        self.volumes = volumes
        if liveness_probe != None and liveness_probe.get('httpGet',None) != None:
            self.liveness_probe = HttpProbe(**liveness_probe)
        elif liveness_probe != None and liveness_probe.get('tcpSocket',None) != None:
            self.liveness_probe = TcpProbe(**liveness_probe)
        elif liveness_probe != None:
            self.liveness_probe = Probe(**liveness_probe)
        if readiness_probe != None and readiness_probe.get('httpGet',None) != None:
            self.readiness_probe = HttpProbe(**readiness_probe)
        elif readiness_probe != None and readiness_probe.get('tcpSocket',None) != None:
            self.readiness_probe = TcpProbe(**readiness_probe)
        elif readiness_probe != None:
            self.readiness_probe = Probe(**readiness_probe)

    def __repr__(self):
        return f"name:{self.name} image:{self.image} id:{self.identity} limits:{self.limits}"



class System:
    """ Distributed system of interacting containerized software. """
    def __init__(self, config, name, principal, service_account, conn_string, proxy_rewrite_rule, containers, identifier, services={}, security_context={}):
        """ Construct a new abstract model of a system given a name and set of containers.
        
            Serves as context for the generation of compute cluster specific artifacts.

            :param config: Configuration information.
            :type name: `Config`
            :param name: Name of the system.
            :type name: str
            :param containers: List of container specifications.
            :type containers: list of containers
        """
        self.config = config
        self.identifier = identifier
        self.system_name = name
        self.amb = False
        self.dev_phase = os.getenv('DEV_PHASE', "prod")
        self.name = f"{name}-{self.identifier}"
        assert self.name is not None, "System name is required."
        containers_exist = len(containers) > 0
        none_are_null = not any([ c for c in containers if c == None ])
        assert containers_exist and none_are_null, "System container elements may not be null."
        logger.info(f"=======> Constructing system from containers = {containers}")
        self.containers = list(map(lambda v : Container(**v), containers)) \
                          if isinstance(containers[0], dict) else \
                             containers
        """ Construct a map of services. """
        self.services = {
            service_name : Service(**service_def)
            for service_name, service_def in services.items ()
        }
        for name, service in self.services.items ():
            service.name = f"{name}-{self.identifier}"
            service.name_noid =  name
        self.volumes = Volumes(self.identifier, containers).process_volumes()
        self.source_text = None
        self.system_port = None
        self.ambassador_id = self._get_ambassador_id()
        """ System environment variables """
        self.system_env = dict(principal)
        """ System tags """
        self.username = principal.get("username")
        self.annotations = {}
        self.namespace = "default"
        self.serviceaccount = service_account
        self.enable_init_container = os.environ.get("TYCHO_APP_ENABLE_VOLUME_PERMISSIONS_INIT_CONTAINER", "false")
        self.conn_string = conn_string
        """PVC flags and other variables for default volumes"""
        self.create_home_dirs = os.environ.get("CREATE_HOME_DIRS", "false").lower()
        self.stdnfs_pvc = os.environ.get("STDNFS_PVC", "stdnfs")
        self.parent_dir = os.environ.get('PARENT_DIR', 'home')
        self.subpath_dir = os.environ.get('SUBPATH_DIR', self.username)
        self.shared_dir = os.environ.get('SHARED_DIR', 'shared')
        """Default UID and GID for the system"""
        default_security_context = self.config.get('tycho')['compute']['system']['defaults']['securityContext']
        self.default_run_as_user = default_security_context.get('uid', '1000')
        self.default_run_as_group = default_security_context.get('gid', '1000')
        """Override container security context"""
        self.security_context = security_context
        """Resources and limits for the init container"""
        self.init_cpus = os.environ.get("TYCHO_APP_INIT_CPUS", "250m")
        self.init_memory = os.environ.get("TYCHO_APP_INIT_MEMORY", "250Mi")
        """Proxy rewrite rule for ambassador service annotations"""
        self.proxy_rewrite_rule = proxy_rewrite_rule

    @staticmethod
    def set_security_context(sc_from_registry):
        security_context: dict[str, Any] = {}
        if os.environ.get("TYCHO_APP_RUN_AS_USER"):
            security_context["run_as_user"] = os.environ.get("TYCHO_APP_RUN_AS_USER")
        else:
            security_context["run_as_user"] = sc_from_registry.get("runAsUser")
        if os.environ.get("TYCHO_APP_RUN_AS_GROUP"):
            security_context["run_as_group"] = os.environ.get("TYCHO_APP_RUN_AS_GROUP")
        else:
            security_context["run_as_group"] = sc_from_registry.get("runAsGroup")
        if os.environ.get("TYCHO_APP_FS_GROUP"):
            security_context["fs_group"] = os.environ.get("TYCHO_APP_FS_GROUP")
        else:
            security_context["fs_group"] = sc_from_registry.get("fsGroup")
        return security_context

    def _get_ambassador_id(self):
        return os.environ.get("AMBASSADOR_ID", "")
    
    @staticmethod
    def get_identifier():
        return uuid.uuid4().hex

    def _get_init_resources(self):
        resources = self.config.get('tycho')['compute']['system']['defaults']['services']['init']['resources']
        return resources

    def get_namespace(self, namespace="default"):
        try:
           with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as secrets:
               for line in secrets:
                   namespace = line
                   break
        except Exception as e:
            logger.warning(f"error getting namespace from file: {e}")
        return namespace

    def requires_network_policy (self):
        return any ([ len(svc.clients) > 0 for name, svc in self.services.items () ])
    
    def render (self, template, context={}):
        """ Supply this system as a context to a template.
        
            :param template: Template 
        """
        final_context = { "system" : self }
        for n, v in context.items ():
            final_context[n] = v
        generator = TemplateUtils (config=self.config)
        template = generator.render (template, context=final_context)
        logger.debug (f"--generated template: {template}")
        return template

    @staticmethod
    def parse (config, name, principal, system, service_account, env={}, services={}):
        """ Construct a system model based on the input request.

            Parses a docker-compose spec into a system specification.
        
            :param name: Name of the system.
            :param system: Parsed docker-compose specification.
            :param env: Dictionary of settings.
            :param services: Service specifications - networking configuration.
        """
        security_context = System.set_security_context(system.get("security_context", {}))
        enable_init_container = System.enable_init_container(security_context)
        principal = json.loads(principal)
        identifier = System.get_identifier()
        containers = []
        if env != None:
            env['identifier'] = identifier
            env['username'] = principal.get('username',"Unknown")
            system_port = None
            for cname,spec in system.get('services',{}).items():
                 env['system_name'] = cname
                 for p in spec.get('ports', []):
                     if ':' in p: system_port = p.split(':')[1]
                     else: system_port = p
                     break
            if system_port != None: env['system_port'] = system_port
            else: env['system_port'] = 8000
            logger.debug ("applying environment settings.")
            system_template = yaml.dump (system)
            logger.debug (json.dumps(env,indent=2))
            system_rendered = TemplateUtils.render_text(template_text=system_template,context=env)
            logger.debug (f"applied settings:\n {system_rendered}")
            for system_render in system_rendered:
                system = system_render

        """ Model each service. """
        logger.debug (f"compose {system}")
        for cname, spec in system.get('services', {}).items ():
            """ Entrypoint may be a string or an array. Deal with either case."""
            ports = []
            expose = []
            env_all = []
            entrypoint = spec.get ('entrypoint', '')
            """ Adding default volumes to the system containers """
            if spec.get('volumes') == None:
                spec.update({'volumes': []})
            rep = {
                'stdnfs_pvc': os.environ.get('STDNFS_PVC', 'stdnfs'), 
                'username': principal.get("username"),
                'parent_dir': os.environ.get('PARENT_DIR', 'home'),
                'subpath_dir': os.environ.get('SUBPATH_DIR', principal.get("username")),
                'shared_dir': os.environ.get('SHARED_DIR', 'shared'),
            }
            if os.environ.get("DEV_PHASE", "prod") != "test":
                try:
                    for volume in config.get('tycho')['compute']['system']['volumes']:
                        createHomeDirs = os.environ.get('CREATE_HOME_DIRS', "true")
                        volSplit = volume.split(":")
                        if createHomeDirs == "false" and ("username" in volume or "shared_dir" in volSplit[1]):
                            continue
                        if createHomeDirs == "true" and ("shared_dir" not in volSplit[1] and "subpath_dir" not in volSplit[2]):
                            continue
                        for k, v in rep.items():
                            volume = volume.replace(k, v)
                        spec.get('volumes', []).append(volume)
                except Exception as e:
                    logger.info("No volumes specified in the configuration.")
            """ Adding entrypoint to container if exists """
            if isinstance(entrypoint, str):
                entrypoint = entrypoint.split ()
            for p in spec.get('ports', []):
              if ':' in p:
                ports.append({
                  'containerPort': p.split(':')[1]
                })
              else:
                ports.append({
                  'containerPort': p
                })
            for e in spec.get('expose', []):
              expose.append({
                'containerPort': e
              })
            """Parsing env variables"""
            env_from_spec = (spec.get('env', []) or spec.get('environment', []))
            env_from_registry = [f"{ev}={os.environ.get('STDNFS_PVC')}" if '$STDNFS' in env[ev] else f"{ev}={env[ev]}" for ev in env]
            env_all = env_from_spec + env_from_registry
            if spec.get("ext",None) != None and spec.get("ext").get("kube",None) != None:
                liveness_probe = spec["ext"]["kube"].get('livenessProbe',None)
                readiness_probe = spec["ext"]["kube"].get('readinessProbe',None)
                if isinstance(liveness_probe,str) and liveness_probe == "none": liveness_probe = None
                if isinstance(readiness_probe,str) and readiness_probe == "none": readiness_probe = None
            else:
                liveness_probe = None
                readiness_probe = None
            containers.append({
                "name": cname,
                "image": spec['image'],
                "command": entrypoint,
                "env": env_all,
                "limits": spec.get('deploy',{}).get('resources',{}).get('limits',{}),
                "requests": spec.get('deploy',{}).get('resources',{}).get('reservations',{}),
                "ports": ports,
                "expose": expose,
                "depends_on": spec.get("depends_on", []),
                "volumes": [v for v in spec.get("volumes", [])],
                "liveness_probe": liveness_probe,
                "readiness_probe": readiness_probe
            })
        system_specification = {
            "config": config,
            "name": name,
            "principal": principal,
            "service_account": service_account,
            "conn_string": spec.get("conn_string", ""),
            "proxy_rewrite_rule": spec.get("proxy_rewrite_rule", False),
            "containers": containers,
            "identifier": identifier,
            "services": services,
            "security_context": security_context,
        }
        logger.debug (f"parsed-system: {json.dumps(system_specification, indent=2)}")
        system = System(**system_specification)
        system.source_text = yaml.dump (system)
        return system

    def __repr__(self):
        return f"name:{self.name} containers:{self.containers}"


class ModifySystem:
    """
       This is a class representation of a system's metadata and specs that needs to be modified.

       :param config: A default config for Tycho
       :type config: A dict
       :param guid: A unique guid to a system/deployment
       :type guid: The UUID as a 32-character hexadecimal string
       :param labels: A dictionary of labels that are applied to deployments
       :type labels: A dictionary
       :param resources: A dictionary containing cpu and memory as keys
       :type resources: A dictionary
       :param containers: A list of containers that are applied to resources
       :type containers: A list of Kubernetes V1Container objects, optional
    """
    def __init__(self, config, patch, guid, labels, resources):
        """
           A constructor method to ModifySystem
        """
        self.config = config
        self.patch = patch
        self.guid = guid
        self.labels = labels
        self.resources = resources
        self.containers = []

    @staticmethod
    def parse_modify(config, guid, labels, cpu, memory):
        """
           Returns an instance of :class:`tycho.model.ModifySystem` class

           :returns: An instance of ModifySystem class
           :rtype: A class object
        """

        resources = {}
        if cpu is not None:
            resources.update({"cpu": cpu})
        if memory is not None:
            resources.update({"memory": memory})

        if len(resources) > 0 or len(labels) > 0:
            patch = True
        else:
            patch = False

        modify_system = ModifySystem(
            config,
            patch,
            guid,
            labels,
            resources,
        )
        return modify_system

    def __repr__(self):
        return f"name: {self.guid} labels: {self.labels} resources: {self.resources}"


class Service:
    """ Model network connectivity rules to the system. """
    def __init__(self, port=None, clients=[]):
        """ Construct a service object modeling network connectivity to a system. """
        self.port = port
        self.clients = list(map(lambda v: str(ipaddress.ip_network (v)), clients))
        self.name = None
        self.name_noid = None
        
    def __repr__(self):
        return json.dumps (
            f"service: {json.dumps({'port':self.port,'clients':self.clients}, indent=2)}")
