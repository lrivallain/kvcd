# Kubernetes vCD operator

A python based proof of concept of an operator to manage VMware Cloud Director ressources.

* Free software: MIT license
* Documentation: [kvcd.readthedocs.io](https://kvcd.readthedocs.io).

## Features

`kvcd` is a proof-of-concept of a python based kubernetes operator to manage VMware vCloud Director resources.

With this first **preview** release, you can manage the state of **vApp** objects with the following configuration
properties:

* Parent Org (*creation only*)
* Parent Org VDC (*creation only*)
* Name (*creation only*)
* Description
* Fence mode (*creation only*)
* EULAs acceptance (*creation only*)
* Ownership
* Power status: on/off
* deploymentLease
* storageLease
* source catalog: if cloned from vCD library item
* source template: if cloned from vCD library item
* metadata: through the Kubernetes resources annotations: ReadOnly on vCloud Director side.

The operator also populates a `status.backing` dictionnary with the following properties according to the vCloud
Director data:

* UUID
* status
* vcd_vapp_href
* vcd_vdc_href
* owner
* deploymentLeaseInSeconds
* storageLeaseInSeconds
* metadata

If a deviation is detected with the declared `specs` of the object: a reconciliation is made to apply the state from
the declared `specs`.

> It may remains some use-case where the reconciliation will fail like when trying to apply a
power-on expected state on an *expired* object.*

The same reconciliation process will occurs when a change is made to the `specs` object declaration to apply changes
to the *backing* object on vCloud Director.

> Modification of some `specs` properties will be ignored, such as `org`, `vdc`, `fence_mode` or `accept_all_eulas`.

## Installation

### Stable release

To install Kubernetes vCD operator, run this command in your terminal:

```bash
pip install kvcd
```

This is the preferred method to install Kubernetes vCD operator, as it will always install the most recent stable release.

If you don't have [pip](https://pip.pypa.io) installed, this [Python installation guide](https://docs.python-guide.org/en/latest/starting/installation/) can guide you through the process.

### From sources

The sources for Kubernetes vCD operator can be downloaded from the [Github repo](https://github.com/lrivallain/kvcd).

You can clone the public repository:

```bash
git clone git://github.com/lrivallain/kvcd
```

Once you have a copy of the source, you can install it with:

```bash
pip install .
```

## Usage

### Configuration

Create a `.venv` file with the following content, according to your setup:

```bash
# Hostname of the vCloud instance | mandatory
KVCD_VCD_HOST=vcloud.domain

# HTTPS port to the vCloud instance | optional: 443 by default
KVCD_VCD_PORT=443

# Organisation of the vCloud user | mandatory
KVCD_VCD_ORG=orgX

# vCloud credentials to use as a service account | mandatory
KVCD_VCD_USERNAME=kvcd-svc
KVCD_VCD_PASSWORD=**********

# Verify the SSL certificate to connect to vCD instance | optional: yes by default
KVCD_VCD_VERIFY_SSL=yes

# Delay between two refresh of the vCD session | optional: 3600 by default
KVCD_VCD_REFRESH_SESSION_INTERVAL=3600

# Refresh interval of the vCloud instance data for each object | optional: 10 by default
KVCD_REFRESH_INTERVAL=10

# Warming up duration | optional: 30 by default
KVCD_REFRESH_INITIAL_DELAY=30

# Reduce the number of timer checks when the ressource is changed | optional: 10 by default
KVCD_REFRESH_IDLE_DELAY=10

# If you only need a sub part of kvcd, you can cherry pick some modules
# (coma separated syntax) | all by default
# KVCD_ENABLED_MODULES=kvcdusers
```

### Test namespace

For the test, we will deploy a test namespace on the Kubernetes cluster:

```bash
kubectl create namespace "test-kvcd"
```

### Deploy the CRD

Deploy the Custom Resource Definition by using the following commands:

```bash
export KVCD_VERSION="v0.1.0"
kubectl apply -f https://github.com/lrivallain/kvcd/releases/download/${KVCD_VERSION}/kvcd-crds.yaml
```

This will deploy the definitions of objects that are managed by the current operator.

### Run it

The current PoC can be run locally or be embeded in a Kubernetes deployment (with pods, service...).

* The local deployment is easier to debug and troubleshoot but requires that the script remain running
to manage resources.
* The embeded deployment is probably a better choice for a real-use-case but may be more complexe to troubleshoot.

#### Run locally

From your dev machine, with access to the Kubernetes cluster, run the following:

```bash
# Run operator with kopf command and listen to specific namespaces
kopf run -m kvcd.main --namespace="test-kvcd" --verbose
```

#### Run in your K8S cluster

To run the operator in the Kubernetes cluster itself, a new namespace `kvcd-system` is used.
You can deploy the required components by running:

```bash
kubectl apply -f https://github.com/lrivallain/kvcd/releases/download/${KVCD_VERSION}/operator-deployment.yaml

# convert the local .env file to a configMap
kubectl create configmap -n kvcd-system kvcd-config --from-env-file=.env

# ensure that the expected pod is running
kubectl get pod -n kvcd-system

# checking logs
kubectl logs -n kvcd-system -f deployment/kvcd-operator
```

### Test

You can now deploy a test empty vApp to check the behavior of the operator:

```bash
cat << EOF | kubectl apply -f -
---
apiVersion: kvcd.lrivallain.dev/v1
kind: VcdVapp
metadata:
  name: kvcd-test-vapp1
  namespace: test-kvcd
  annotations:
    app: app01
    isprod: "false"
    version: "0.1.0"
spec:
  description: Test description
  org: <name of your org>
  vdc: <name of your org VDC>
  owner: <name of the owner to set>
EOF

kubectl get vcdvapp
```

After a couple of seconds, you should get something like this:

```bash
NAME              ORG        VDC             STATUS       UUID
kvcd-test-vapp1   <org>      <org vdc>       Resolved     urn:vcloud:vapp:a2871e71-49ab-48a4-a6dc-4c11743b7ba7
```

You can now edit fields values, delete or manage the vApp like a kube object.

### Cleanup

```bash
kubectl delete -n test-kvcd vcdvapp kvcd-test-vapp1
kubectl delete namespace test-kvcd
```

If you did deploy the operator in the cluster and you want to remove it:

```bash
kubectl delete ns kvcd-system
```
