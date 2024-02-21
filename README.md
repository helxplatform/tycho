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

#### Label: executor

For each application (pod) that is created is labeled with `executor: tycho` which allows for a concise way to list all of the pods that it creates

    kubectl get pods -l executor=tycho


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
