import argparse
import json
import logging
import os
import sys
import traceback
import yaml
import uuid
from kubernetes import client as k8s_client, config as k8s_config
from tycho.model import System
from tycho.tycho_utils import TemplateUtils
import kubernetes.client
from kubernetes.client.rest import ApiException
from tycho.exceptions import DeleteException

logger = logging.getLogger (__name__)

class Compute:
    """ Abstraction of a compute cluster. """
    def start (self, system):
        pass
class DockerComposeCompute(Compute):
    def start (self, system, namespace="default"):        
        """ Generate a globally unique identifier for the application. All associated objects will share this identifier. """
        system.name = f"{system.name}-{uuid.uuid4().hex}"
        docker_compose = f"{system.name}-docker-compose.yaml"

        with open (docker_compose, 'w') as stream:
            import yaml
            from compose.cli.main import TopLevelCommand, project_from_options
            yaml.dump (compose, stream)

        options = {
            "--no-deps": False,
            "--abort-on-container-exit": False,
            "SERVICE": "",
            "--remove-orphans": False,
            "--no-recreate": True,
            "--force-recreate": False,
            "--build": False,
            '--no-build': False,
            '--no-color': False,
            "--rmi": "none",
            "--volumes": "",
            "--follow": False,
            "--timestamps": False,
            "--always-recreate-deps": False,
            "--tail": "all",
            "-d": True,
        }
        print (__file__)
        #project = project_from_options(os.path.dirname(__file__), options)
        project = project_from_options(os.getcwd(), options)
        cmd = TopLevelCommand(project)
        def oh_my ():
            cmd.up(options)
            def fin():
                cmd.logs(options)
                cmd.down(options)
            request.addfinalizer(fin)
        from_worker ([ oh_my ])
        return {}

    '''
        with open(docker_compose, "w") as stream:
            os.system 
    '''
    def delete (self, name, namespace="default"):
        pass
    
class KubernetesCompute(Compute):
    """ A Kubernetes specific implementation. """

    def __init__(self):
        """ Initialize connection to Kubernetes. """
        """ TODO: Authentication. """
        super(KubernetesCompute, self).__init__()
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            k8s_config.load_incluster_config()
        else:
            k8s_config.load_kube_config()
        api_client = k8s_client.ApiClient()
        self.api = k8s_client.CoreV1Api(api_client)
        self.extensions_api = k8s_client.ExtensionsV1beta1Api(api_client)

    def start (self, system, namespace="default"):
        """ From the end user perspective, this probably entails creating 
        - The pod
        - The deployment
        - The service
        """

        try:

            system.name = f"{system.name}-{system.identifier}"
            
            """ Turn an abstract system model into a cluster specific representation. """
            pod_manifest = system.project ("kubernetes-pod.yaml")

            utils = TemplateUtils ()            
            pvc_manifest = utils.render(template="pvc.yaml",
                                        context={
                                            "system": system,
                                        })

            response = self.api.create_namespaced_persistent_volume_claim(
                namespace='default',
                body=pvc_manifest)

            pv_raw = system.name.split("-")
            pv_raw.pop(len(pv_raw)-1)
            pv_name = "-".join(pv_raw)
            logger.debug (f"PV NAME {pv_name}", pv_name)
            pv_manifest = utils.render(template="pv.yaml",
                                       context={
                                           "system": system,
                                           "pv_name": pv_name
                                       })
            response = self.api.create_persistent_volume(body=pv_manifest)

            """ Create the generated pod in kube. """
            pod_spec = self.api.create_namespaced_pod(
                body=pod_manifest,
                namespace='default')
        
            """ Create a deployment for the pod. """
            deployment = self.pod_to_deployment (
                name=system.name,
                template=pod_spec,
                namespace=namespace) 
        except Exception as e:
            self.delete (system.name)
            exc_type, exc_value, exc_traceback = sys.exc_info()
            text = traceback.format_exception(
                exc_type, exc_value, exc_traceback)
            raise StartException (
                message=f"Unable to start system: {system.name}",
                details=text)
        
        """ one port mappable per container for now. """
        container_map = {}
        for container in system.containers:
            if len(container.ports) != 1:
                continue

            container_port = container.ports[0]['containerPort']
            logger.debug (f"Creating service exposing container {container.name} on port {container_port}")

            """ render the service template. """
            utils = TemplateUtils ()
            service_manifest=utils.render (template="service.yaml",
                                           context={
                                               "system" : system,
                                               "container_port" : container_port
                                           })

            response = self.api.create_namespaced_service(
                body=service_manifest,
                namespace='default')
            container_map[container.name] = {
                port.name : port.node_port for port in response.spec.ports
            }
        return {
            'name' : system.name,
            'sid' : system.identifier,
            'containers' : container_map
        }

    def pod_to_deployment (self, name, template, namespace="default"):
        
        """ Create a deployment specification. """
        deployment_spec = k8s_client.ExtensionsV1beta1DeploymentSpec(
            replicas=1,
            template=template)
        
        """ Instantiate the deployment object """
        deployment = k8s_client.ExtensionsV1beta1Deployment(
            api_version="extensions/v1beta1",
            kind="Deployment",
            metadata=k8s_client.V1ObjectMeta(name=name),
            spec=deployment_spec)

        """ Create the deployment. """
        api_response = self.extensions_api.create_namespaced_deployment(
            body=deployment,
            namespace=namespace)
        #print(f"Deployment created. status={api_response.status}")
        return deployment

    def log_status (self, response):
        if not response.status or response.status == 'Success':
            logger.debug ("--succeeded")
        elif response.status == 'Failure':
            logger.error (f"--failed: {response}")
    def delete (self, name, namespace="default"):
        """ Delete the deployment. """
        try:
            logger.info (f" --deleting deployment {name} in namespace {namespace}")
            response = self.extensions_api.delete_collection_namespaced_deployment(
                label_selector=f"tycho-guid={name}",
                namespace=namespace)
            self.log_status (response)
            
            logger.info (f" --deleting replica_set {name} in namespace {namespace}")
            response = self.extensions_api.delete_collection_namespaced_replica_set(
                label_selector=f"tycho-guid={name}",
                namespace=namespace)
            self.log_status (response)
        
            """ Delete the service. No obvious collection based api for service deletion. """
            service_list = self.api.list_namespaced_service(
            label_selector=f"tycho-guid={name}", namespace=namespace)
            for service in service_list.items:
                if service.metadata.labels.get ("tycho-guid", None) == name:
                    logger.info (f" --deleting service {name} in namespace {namespace}")
                    response = self.api.delete_namespaced_service(
                        name=service.metadata.name,
                        body={},
                        namespace=namespace)
                    self.log_status (response)
                
            logger.info (f" --deleting pod {name} in namespace {namespace}")
            response = self.api.delete_collection_namespaced_pod(
                label_selector=f"tycho-guid={name}",
                namespace=namespace)
            self.log_status (response)

            logger.info (f" --deleting persistent volume {name} in namespace {namespace}")
            response = self.api.delete_collection_persistent_volume(
                label_selector=f"tycho-guid={name}")
            self.log_status (response)
            
            logger.info (f" --deleting persistent volume claim {name} in namespace {namespace}")
            response = self.api.delete_collection_namespaced_persistent_volume_claim(
                label_selector=f"tycho-guid={name}",
                namespace=namespace)
            self.log_status (response)
        
        except ApiException as e:
            traceback.print_exc (e)
            exc_type, exc_value, exc_traceback = sys.exc_info()
            text = traceback.format_exception(
                exc_type, exc_value, exc_traceback)
            raise DeleteException (
                message=f"Failed to delete system: {name}",
                details=text)
        return {
        }
    
    def status (self, name=None, namespace="default"):
        """ Get status.
        Without a name, this will get status for all running systems.
        With a name, it will get status for the specified system.
        """
        result = []
        response = self.extensions_api.list_namespaced_deployment (
            namespace,
            label_selector=f"executor=tycho")
        if response:
            #print(f"** response: {response}")
            for item in response.items:
                result.append ({
                    "name" : item.metadata.name,
                    "sid"  : item.metadata.labels.get ("tycho-guid", None)
                })
        return result
