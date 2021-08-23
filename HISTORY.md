# History


## 0.1.0 (2021-08-13)

* First release on PyPI.

`kvcd` is a proof-of-concept of a python based kubernetes operator to manage VMware vCloud Director resources.

With this first **preview** release, you can manage the state of vApp objects with the following configuration items:

* Org (*creation only*)
* Org VDC (*creation only*)
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

If a deviation is detected with the declared `specs` of the object: a reconcialiation is made to apply the state from
the declared `specs`.

> It may remains some use-case where the reconcialiation will fail like when trying to apply a
power-on expected state on an *expired* object.*

The same reconcialiation process will occurs when a change is made to the `specs` object declaration to apply changes
to the *backing* object on vCloud Director.

> Modification of some `specs` properties will be ignored, such as `org`, `vdc`, `fence_mode` or `accept_all_eulas`.
