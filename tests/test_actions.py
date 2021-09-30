import os
import json
import logging
import pytest
import yaml
from tycho.client import TychoClient
from tycho.test.lib import client
from tycho.test.lib import system
from tycho.test.lib import system_request
from unittest import mock

from tycho.actions import StartSystemResource
from tycho.actions import TychoResource
from tycho.actions import DeleteSystemResource
from tycho.actions import StatusSystemResource
from tycho.actions import ModifySystemResource

logger = logging.getLogger(__name__)


def test_tycho ():
    backplane = None
    tycho_object = Tycho(backplane=backplane)
    assert tycho_object['error'] != 'error'


def test_start_system_resource(mocker, system_request, client, request):
    print ("{request.node.name}")
    response = {
        "status": "success"
    }

    # Making a system request, storing in tycho_system
    tycho_system = StartSystemResource().post(system_request)

    assert tycho_system['status'] == response['status']
    assert tycho_system['message'].startswith("Started system")


def test_delete_system_resource(mocker, system_request, client, request):
    print("{request.node.name}")
    response = {
        "status": "success"
    }

    tycho_delete = DeleteSystemResource().post(system_request)
    print(tycho_delete)

    assert tycho_delete['status'] == response['status']
    assert tycho_delete['message'].startswith("Deleted")


def test_status_system_resource(mocker, system_request, client, request):
    print("{request.node.name}")
    response = {
        "status": "success"
    }

    tycho_status = StatusSystemResource().post(system_request)
    print(tycho_status)

    assert tycho_status['status'] == response['status']
    assert tycho_status['message'].startswith("Get status")


def test_modify_system_resource(mocker, system_request, client, request):
    print("{request.node.name}")
    response = {
        "status": "success"
    }

    tycho_modify = ModifySystemResource().post(system_request)
    print(tycho_modify)

    assert tycho_modify['status'] == response['status']
    assert tycho_modify['message'].startswith("Modified")