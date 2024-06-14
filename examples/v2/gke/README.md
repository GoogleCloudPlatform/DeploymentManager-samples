# GKE Cluster and Type

## Overview

This is a [Google Cloud Deployment
Manager](https://cloud.google.com/deployment-manager/overview) template which
deploys a GKE cluster and a Deployment Manager type. The type can be used by
other deployments to deploy Kubernetes resources into the cluster.

## Getting started

Using Deployment Manager to deploy Kubernetes resources into a new GKE cluster
is a two step process, as described below.

### Deploy a cluster

When ready, deploy with the following command:

    NAME="your-name"
    ZONE="your-zone"
    CLUSTER_VERSION="your-cluster-version"
    MACHINE_TYPE="your-machine-type"
    gcloud deployment-manager deployments create ${NAME} \
    --template cluster.py \
    --properties zone:${ZONE},clusterVersion:${CLUSTER_VERSION},machineType:${MACHINE_TYPE}

This will result in two resources:

* a GKE cluster named `${NAME}-cluster-py`
* a Deployment Manager type named `${NAME}-cluster-py-type`

The type can now be used in other deployments to deploy kubernetes resources
using the cluster API.

### Deploying Kubernetes resources

Using `deployment.yaml`, create a `Deployment` and a `Service`
to the GKE cluster created in the last step. Fill in the following information
before deploying:

* The cluster type created for the GKE cluster deployed previously. This will
  be `${NAME}-cluster-py-type`, visible in the developers console.
* Optionally, change the `docker` image to run.
* Optionally, specify the port exposed by the image.

When ready, deploy with the following command. When you provide the template, 
then you must provide all of its properties, e.g.

    IMAGE=gcr.io/deployment-manager-examples/nodejsservicestatic
    PORT=80
    gcloud deployment-manager deployments create deployment \
    --template deployment.py \
    --properties clusterType:${NAME}-cluster-py-type,image:${IMAGE},port:${PORT}

Or:

    IMAGE=nginx
    PORT=80
    gcloud deployment-manager deployments create deployment \
    --template deployment.py \
    --properties clusterType:${NAME}-cluster-py-type,image:${IMAGE},port:${PORT}


### Verifying deployment

Be sure your `kubectl` command-line tool is set up to communicate with the
cluster you have deployed:

    gcloud container clusters get-credentials ${NAME}-cluster-py --zone ${ZONE}

Now you can see the resources that have been deployed using `kubectl`:

    kubectl get deployments
    kubectl get services

For security reasons, the Kubernetes Service is *not* exposed externally. There are 2
 easy ways to access the Service using port-forwarding:

First, we can use `kubectl` and port-forward from one of the Kubernetes Pods (`${PORT}`)to our localhost (`:9999`). Assuming this is the only Service (and only Pod) deployed to this cluster:

    kubectl port-forward $(\
      kubectl get pods --output=jsonpath="{.items[0].metadata.name}") \
      9999:${PORT}

You may then:

    curl localhost:9999

Second, we can use `gcloud compute ssh` to port-forward from one of the Kubernetes Nodes using the Service's `NodePort` to our localhost (`:9999`):

Let's grab one of our cluster's nodes at random:

    NODES=$(kubectl get nodes --output=name | sed 's|node/||g')
    NODE_HOST=$(shuf -n1 -e ${NODES})

Let's determine the `NodePort` of our Service; it is exposed on every Node:

    NODE_PORT=$(\
      kubectl get services \
      --selector=id=deployment-manager \
      --output=jsonpath="{.items[0].spec.ports[0].nodePort}")
    echo "From another session, browse or curl http://localhost:${NODE_PORT}"

    gcloud compute ssh ${NODE_HOST} --ssh-flag="-L ${NODE_PORT}:localhost:${NODE_PORT}"

From a second session, you may then browse or:

    curl localhost:${NODE_PORT}

## Important Note

When deploying into a Kubernetes cluster with Deployment Manager, it is
important to be aware that deleting `Deployment` Kubernetes objects
**does not delete the underlying pods**, and it is your responsibility to
manage the destruction of these resources when deleting a
`Deployment` in your configuration.