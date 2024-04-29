import argparse
import ipaddress
import json
import jsonschema
import logging
import netifaces
import os
import requests
import sys
import traceback
import yaml
from tycho.core import Tycho
from tycho.tycho_utils import NetworkUtils

"""
Provides actions for creating, monitoring, and deleting distributed systems of cloud native
containers running on abstracted compute fabrics. 
 
"""
logger = logging.getLogger(__name__)

""" Load the schema. """
schema_file_path = os.path.join (
    os.path.dirname(__file__),
    'api-schema.yaml')
template = None
with open(schema_file_path, 'r') as file_obj:
    template = yaml.load(file_obj, Loader=yaml.FullLoader) #nosec B506

backplane = None
_tycho = Tycho(backplane=backplane)


def tycho ():
    return _tycho


class TychoResource:
    """ Base class handler for Tycho requests. """
    def __init__(self):
        self.specs = {}
        
    """ Functionality common to Tycho services. """
    def validate(self, request, component):
        """ Validate a request against the schema. """
        if not self.specs:
            with open(schema_file_path, 'r') as file_obj:
                self.specs = yaml.load(file_obj, Loader=yaml.FullLoader) #nosec B506
        to_validate = self.specs["components"]["schemas"][component]
        try:
            logger.debug(f"--:Validating obj {request}")
            logger.debug(f"  schema: {json.dumps(to_validate, indent=2)}")
            jsonschema.validate(request, to_validate)
        except jsonschema.exceptions.ValidationError as error:
            logger.error(f"ERROR: {str(error)}")
            traceback.print_exc()

    def create_response(self, result=None, status='success', message='', exception=None):
        """ Create a response. Handle formatting and modifiation of status for exceptions. """
        if exception:
            traceback.print_exc()
            status = 'error'
            exc_type, exc_value, exc_traceback = sys.exc_info()
            message = f"{exception.args[0]} {''.join (exception.args[1])}" \
                if len(exception.args) == 2 else exception.args[0]
            result = {
                'error': message
            }
        return {
            'status': status,
            'result': result,
            'message': message
        }


class StartSystemResource(TychoResource):
    """ Parse, model, emit orchestrator artifacts and execute a system. """
    
    """ System initiation. """
    def post(self, request):
        response = {}
        try:
            logger.info(f"actions.StartSystemResource.post - start-system: {json.dumps(request, indent=2)}")
            self.validate(request, component="System")
            system = tycho().parse(request)
            response = self.create_response(
                result=tycho().get_compute().start(system),
                message=f"Started system {system.name}")
        except Exception as e:
            response = self.create_response(
                exception=e,
                message=f"Failed to create system.")
        return response


class DeleteSystemResource(TychoResource):
    """ System termination. Given a GUID for a Tycho system, use Tycho core to eliminate all
    components comprising the running system."""
    def post(self, request):
        response = {}
        system_name = None
        try:
            logger.debug(f"delete-request: {json.dumps(request, indent=2)}")
            self.validate(request, component="DeleteRequest")
            system_name = request['name']
            response = self.create_response(
                result=tycho().get_compute().delete(system_name),
                message=f"Deleted system {system_name}")
        except Exception as e:
            response = self.create_response(
                exception=e,
                message=f"Failed to delete system {system_name}.")
        return response


class StatusSystemResource(TychoResource):
    """ Status executing systems. Given a GUID (or not) determine system status. """

    def post(self, request):
        response = {}
        try:
            logging.debug(f"list-request: {request}")
            self.validate(request, component="StatusRequest")
            system_name = request.get('name', None)
            system_username = request.get('username', None)
            response = self.create_response(
                result=tycho().get_compute().status(system_name, system_username),
                message=f"Get status for system {system_name}")
        except Exception as e:
            response = self.create_response(
                exception=e,
                message=f"Failed to get system status.")
        print(json.dumps(response, indent=2))
        return response


class ModifySystemResource(TychoResource):
    """ Modify a system given a name, labels, resources(cpu and memory) """

    def post(self, request):
        try:
            logging.debug(f"System specs to modify: {request}")
            system_modify = tycho().parse_modify(request)
            response = self.create_response(
                result=tycho().get_compute().modify(system_modify),
                message=f"Modified the system")
        except Exception as e:
            response = self.create_response(
                exception=e,
                message=f"Failed to modify system status.")
        return response
