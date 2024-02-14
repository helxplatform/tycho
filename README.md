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

## Quick Start


### Architecture
![image](https://user-images.githubusercontent.com/306971/60749878-ada4fa00-9f6e-11e9-9fb8-d720cf78c41d.png)

## Install

* Install python 3.7.x or greater.
* Create a virtual environment.
* Install the requirements.
* Start the server.

```
python3 -m venv environmentName
source environmentName/bin/activate
pip install -r requirements.txt
export PATH=<tycho-repo-dir>/bin:$PATH
tycho api
```

### Usage - A. Development Environment Next to Minikube

This mode uses a local minikube instance with Tycho running outside of Minikube. This is the easiest way to add and test new features quickly.

Run minikube:
```
minikbue start
```
Run the minikube dashboard:
```
minikube dashboard
```
Run the Tycho API:
```
cd tycho
PYTHONPATH=$PWD/.. python api.py
```

Launch the Swagger interface `http://localhost:5000/apidocs/`.
![image](https://user-images.githubusercontent.com/306971/53313133-f1337d00-3885-11e9-8aea-83ab4a92807e.png)

Use the Tycho CLI client as shown above or invoke the API.

### Usage - B. Development Environment Within Minikube

When we deploy Tycho into Minikube it is now able to get its Kubernetes API configuration from within the cluster.

In the repo's kubernetes directory, we define deployment, pod, service, clusterrole, and clusterrolebinding models for Tycho. The following interaction shows deploying Tycho into Minikube and interacting with the API.

We first deploy all Kubernetes Tycho-api artifacts into Minkube:
```
(tycho) [scox@mac~/dev/tycho/tycho]$ kubectl create -f ../kubernetes/
deployment.extensions/tycho-api created
pod/tycho-api created
clusterrole.rbac.authorization.k8s.io/tycho-api-access created
clusterrolebinding.rbac.authorization.k8s.io/tycho-api-access created
service/tycho-api created
```
Then we use the client as usual.

### Usage - C. Within Google Kubernetes Engine from the Google Cloud Shell

Starting out, Tycho's not running on the cluster:
![image](https://user-images.githubusercontent.com/306971/60748993-b511d680-9f61-11e9-8851-ff75ca74d079.png)

First deploy the Tycho API 
```
$ kubectl create -f ../kubernetes/
deployment.extensions/tycho-api created
pod/tycho-api created
clusterrole.rbac.authorization.k8s.io/tycho-api-access created
clusterrolebinding.rbac.authorization.k8s.io/tycho-api-access created
service/tycho-api created
```

Note, here we've edited the Tycho service def to create the service as type:LoadBalancer for the purposes of a command line demo. In general, we'll access the service from within the cluster rather than exposing it externally.

That runs Tycho:
![image](https://user-images.githubusercontent.com/306971/60748922-c73f4500-9f60-11e9-8d48-fb49902dc836.png)

Initialize the Tycho API's load balancer IP and node port. 
```
$ lb_ip=$(kubectl get svc tycho-api -o json | jq .status.loadBalancer.ingress[0].ip | sed -e s,\",,g)
$ tycho_port=$(kubectl get service tycho-api --output json | jq .spec.ports[0].port)
```
Launch an application (deployment, pod, service). Note the `--command` flag is used to specify the command to run in the container. We use this to specify a flag that will cause the notebook to start without prompting for authentication credentials.
```
$ PYTHONPATH=$PWD/.. python client.py --up -n jupyter-data-science-3425 -c jupyter/datascience-notebook -p 8888 --command "start.sh jupyter lab --LabApp.token='
'"
200
{
  "status": "success",
  "result": {
    "containers": {
      "jupyter-data-science-3425-c": {
        "port": 32414
      }
    }
  },
  "message": "Started system jupyter-data-science-3425"
}
```
Refreshing the GKE cluster monitoring UI will now show the service starting:
![image](https://user-images.githubusercontent.com/306971/60749371-15574700-9f67-11e9-81cf-77ccb6724a08.png)

Then running
![image](https://user-images.githubusercontent.com/306971/60749074-e8a13080-9f62-11e9-81d2-37f6cdbfc9dc.png)

Get the job's load balancer ip and make a request to test the service.
```
$ job_lb_ip=$(kubectl get svc jupyter-data-science-3425 -o json | jq .status.loadBalancer.ingress[0].ip | sed -e s,\",,g)
$ wget --quiet -O- http://$job_lb_ip:8888 | grep -i /title
    <title>Jupyter Notebook</title>
```
From a browser, that URL takes us directly to the Jupyter Lab IDE:
![image](https://user-images.githubusercontent.com/306971/60755934-dfe14680-9fc4-11e9-9d3b-d3f32539621d.png)

And shut the service down:
```
$ PYTHONPATH=$PWD/.. python client.py --down -n jupyter-data-science-3425 -s http://$lb_ip:$tycho_port
200
{
  "status": "success",
  "result": null,
  "message": "Deleted system jupyter-data-science-3425"
}
```
This removes the deployment, pod, service, and replicasets created by the launcher.

### Client Endpoint Autodiscovery

Using the command lines above without the `-s` flag for server will work on GKE. That is, the client is created by first using the K8s API to locate the Tycho-API endpoint and port. It builds the URL automatically and creates a TychoAPI object ready to use.
```
client_factory = TychoClientFactory ()
client = client_factory.get_client ()
```

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
