# Tycho

[![PyPI](https://img.shields.io/pypi/v/tycho-api?label=tycho)](https://pypi.org/project/tycho-api/)
[![Build-Project](https://github.com/helxplatform/tycho/actions/workflows/build-project.yml/badge.svg)](https://github.com/helxplatform/tycho/actions/workflows/build-project.yml)
[![flake8](https://github.com/helxplatform/tycho/actions/workflows/flake8.yml/badge.svg)](https://github.com/helxplatform/tycho/actions/workflows/flake8.yml)

## Introduction

Tycho is an python module to perform CRUD on HeLx Apps.  More speficially, a HeLx App is a kubernetes pod created by [HeLx Appstore](https://github.com/helxplatform/appstore) with certain specializations; these specializations (for example username) are connected to the pod in a typical kubernetes way such a label.  Additionally, other properties such as user home directory, user permissions, etc are also enabled.  Underlying this is a HeLx App Model (System) the values of which support these features.  That model is storable in a django database, and is used by appstore to keep track of that per user session.

### Use of templates

An important feature of of tycho is the use of [Jinja](https://github.com/pallets/jinja) that allows a system to be converted to a syntax needed for kubernetes.  This allows for a sussinct way to express the important components of an App is, and then allow jinja's engine to make it readable by Kubernetes.

### Interaction, assumption of Ambassador

Tycho also communicates with Ambassador to set up the authentication mechanism to allow access to only users for which the app is set.


* A subset of [docker-compose](https://docs.docker.com/compose/) is the system specification syntax.
* [Kubernetes](https://kubernetes.io/) is the first supported orchestrator.

## Goals

* **Application Simplity**: The Kubernetes API is reliable, extensive, and well documented. It is also large, complex, supports a range of possibilities greater than many applications need, and often requires the creation and control of many objects to execute comparatively simple scenarios. Tycho bridges the simplicity of Compose to the richness of the Kubernetes' architecture.
* **Lifecycle Management**: Tycho treats distributed systems as programs whose entire lifecycle can be programmatically managed.
* **Pluggable Orchestrators**: The Tycho compiler abstracts clients from the orchestrator. It creates a system model and generates orchestrator specific artifacts.
* **Policy**: Best practices for application lifetime, security, networking are handled automatically.

## Prior Art

This work relies on these foundations:
* **[PIVOT](https://renci.org/wp-content/uploads/2019/02/Cloud_19.pdf)**: A cloud agnostic scheduler with an API for executing distributed systems.
* **[Kubernetes](https://kubernetes.io/)**: Widely deployed, highly programmable, horizontally scalable container orchestration platform. 
* **[Kompose](https://docs.docker.com/compose/)**: Automates conversion of Docker Compose to Kubernetes. Written in Go, does not provide an API. Supports Docker Compose to Kubernetes only.
* **[Docker](https://www.docker.com/)**: Pervasive Linux containerization tool chain enabling programmable infrastructure and portability.
* **[Docker-compose](https://docs.docker.com/compose/)**: Syntax and tool chain for executing distributed systems of containers.
* **Docker Swarm**: Docker only container orchestration platform with minimal adoption.

## CI/CD
Github Actions are employed to test and publish development and main releases of tycho to [pypi](https://pypi.org/project/tycho-api/). These releases follow SemVer ('Major', 'Minor', 'Patch') versioning.

To create a main/master pypi package for tycho, the `VERSION` in `tycho/__init__.py` will need to be updated by the developer to the desired stable release version number. 

If testing in the develop branch, editing the `tycho/__init__.py` file will NOT be necessary to generate a pypi package build, as the pypi-dev-upload.yml workflow will create a new tag based on day and time for your testing purposes which is uploaded upon each push to the develop branch. This ".dev" tag does not affect the develop branch code at all. 

This means that a pr from feature branch to develop branch results in an automatic pypi build. If on the same day, a change to the develop branch occurs, then a new build is also generated with a differing ".dev" tag similar to `tycho-api:1.12.0.dev20230221030806`. 

To locate the ".dev" tagged pypi build, navigate to the corresponding workflow run in the `Github Actions` tab, called `build-dev-to-pypi` then click the dropdown for `Publish Package to Pypi` and the link to the package will be provided within. The .dev packages are not searchable in Pypi as this would distract from stable packages of the same name and cause confusion - see pep 440. 

## Development 
1. git clone https://github.com/helxplatform/tycho.git --branch branch_name

tycho is a python package, and is developed using normal python package patterns.  It does require connectivity to kubernetes to test, and preferrable incorporation by appstore.

## Tycho Labels

### Label: executor

For each application (pod) that is created is labeled with `executor: tycho` which allows
for a concise way to list all of the pods that it creates

### Label: app-name

The name of the app (e.g. JupyterLab).  A label to specify what application the
pod/deployment is executing on behalf of.

### Label: name

As above, but extended with a unique-ifying guid

### Label: username

The name of the user who is logged in via helx-appstore for which a
tycho-created pod is executing.

### A useful kubectl

Here is a useful way to list all pods for all users listing the pod, application
name and user for which it's executing
 
    kubectl get pod -l executor=tycho -L app-name -L username --sort-by username

## Source Code

### Tycho System Management (actions.py)

This module provides a set of functionalities to manage distributed systems of cloud-native containers. It allows for creating, monitoring, and deleting systems running on abstracted compute fabrics.

#### Overview

- **TychoResource**: The base class for handling Tycho requests, providing common functionality such as request validation against a predefined schema.
- **StartSystemResource**: Handles system initiation, parsing, modeling, emitting orchestrator artifacts, and executing a system.
- **DeleteSystemResource**: Manages system termination, using a system's GUID to eliminate all its running components.
- **StatusSystemResource**: Provides the status of executing systems, allowing status checks either globally or for specific systems.
- **ModifySystemResource**: Offers functionality to modify a system's specifications like name, labels, and resources (CPU and memory).

#### Key Functions

- `validate(request, component)`: Validates a request against the API schema.
- `create_response(result, status, message, exception)`: Creates a formatted response, handling exceptions and status modifications.
- `post(request)`: For each resource class, processes the POST request to perform the respective actions (start, delete, status check, or modify a system).

### Tycho Client and Services Management (client.py)

This module offers a comprehensive suite of functionalities to manage, monitor, and interact with distributed systems and services, particularly focusing on cloud-native container orchestration using Kubernetes.

#### Key Components

- **TychoService**: Represents a service endpoint, holding details like name, IP address, port, and resource utilization.
- **TychoStatus**: Models the response from a status request, encapsulating the status, services, and messages.
- **TychoSystem**: Represents a running system, handling system status, name, identifier, services, and connection strings.
- **TychoClient**: The core Python client for interacting with the Tycho API, enabling actions like start, status, delete, and modify.
- **TychoClientFactory**: Facilitates locating and connecting to the Tycho API within a Kubernetes cluster.
- **TychoApps**: Manages applications, supporting actions like cloning repositories, extracting metadata, and system specifications.

#### Features

- Service utilization tracking, converting and aggregating resource metrics.
- Comprehensive system representation, including status, service details, and operations.
- Dynamic interaction with Tycho API to start, stop, modify, and retrieve the status of services.
- Environment-sensitive Kubernetes configuration loading for in-cluster or external usage.
- CLI interface for direct interaction, supporting operations like up, down, status, and modify on systems.

### Core (core.py)

The `Tycho` library serves as a sophisticated abstraction layer atop cloud-native container orchestration platforms, enhancing system architecture and policy enforcement. It aims to simplify the design, decision-making, automation, testing, and enforcement processes for teams working with Kubernetes.

## Features
- **Initialization**: Constructs a Tycho component with configurable backplane and system settings.
- **Compute Fabric API**: Provides access to the compute fabric's code emitter based on constructor specifications.
- **System Parsing**: Transforms JSON requests into abstract syntax trees, enabling structured system specifications that include environment variables, services, and networking rules.
- **Modification Parsing**: Allows for the modification of system metadata and specifications based on GUID, labels, and resource allocations.
- **Backplane Validation**: Checks for valid compute backplanes and lists supported backplanes, facilitating integration with various compute fabrics.

Designed to work seamlessly with Kubernetes, Tycho leverages a configuration-first approach, promoting clarity and efficiency in deploying and managing containerized applications.

### TychoContext (context.py)

The `TychoContext` library provides a comprehensive Python interface for loading, understanding, and utilizing application registries within a platform environment. It leverages a declarative metadata repository (YAML-based) to outline available applications, including their basic metadata, repositories for further details, and integration with the Tycho system for app management.

Key Features:
- **Principal Class**: Abstracts system identity with support for access and refresh tokens.
- **App Registry Loading**: Dynamically loads app registry and default configurations from YAML files, supporting modifications via environment variables.
- **Configuration Management**: Includes utilities for merging app configurations and handling inheritance and mixins from different contexts.
- **App Management**: Facilitates starting, stopping, updating, and querying application statuses using the Tycho system, with detailed logging and error handling.
- **Environment and Security**: Manages application environment variables, security contexts, and integrates with Kubernetes for service accounts and resource management.
- **Proxy and Integration Support**: Provides mechanisms for proxy rewrite rules and external integrations like Gitea.

Designed for flexibility and ease of integration, this library supports development and testing phases with a NullContext for mock interactions, alongside the primary TychoContext for live environments.

### "proxy_rewrite" Feature Overview:

The "proxy_rewrite" feature ensures system-wide consistency in handling service 
locations, especially when interacting with higher-level reverse proxies. By def
ining annotations in `service.yaml`, Ambassador's behavior is tailored, allowing
the underlying service to perceive an altered path while maintaining a consistent
location view at the system level.

- **context.py**: Processes external specifications, capturing "proxy_rewrite" 
directives, and transforms them into an internal representation.
- **model.py**: Forms the structural foundation of the system, accurately reflecting
the "proxy_rewrite" configurations and their implications.
- **service.yaml**: Serves as a template for Kubernetes service definitions. When
interpreted, it influences Ambassador's behavior using "proxy_rewrite" annotations,
ensuring path and location consistency across the system.
