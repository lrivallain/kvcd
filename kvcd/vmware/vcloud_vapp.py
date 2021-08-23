"""Kopf based resource management for the vApp objects
"""

import kopf
from kubernetes.client.api import core_v1_api
from kubernetes.client.rest import ApiException
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
from pyvcloud.vcd.vdc import Org
from pyvcloud.vcd.client import VCLOUD_STATUS_MAP
from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.client import MetadataDomain
from pyvcloud.vcd.client import MetadataVisibility
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import BadRequestException
from pyvcloud.vcd.exceptions import OperationNotSupportedException
from pyvcloud.vcd.utils import metadata_to_dict
from datetime import datetime, timezone
import dateutil.parser
from kvcd.utils import str2bool, lowercase_first_string_letter
from kvcd.vmware.vcloud_helper import VcdSession, get_org, get_vdc
from kvcd.main import get_vcd_session, kvcd_config


@kopf.on.resume('kvcd.lrivallain.dev', 'v1', 'vcdvapps')
@kopf.on.create('kvcd.lrivallain.dev', 'v1', 'vcdvapps')
def create_vcdvapp(spec: kopf.Spec, status: kopf.Status, name: str,
    namespace: str, logger: kopf.Logger, patch: kopf.Patch,
    annotations: kopf._cogs.structs.dicts.MappingView,
    **kwargs):
    """Create a vcdvapp from specs

    Args:
        spec (kopf.Spec): Object specs
        status (kopf.Status): Current status data of the object
        name (str): Name of the object
        namespace (str): Name of the namespace where object is declared
        logger (kopf.Logger): Logger facility
        patch (kopf.Patch): Patch to apply
    """
    _created = False
    vdc = get_vdc(
        vcd_session=get_vcd_session(),
        org_name=spec.get('org'),
        vdc_name=spec.get('vdc'))
    if ((status.get('backing', {}).get('vcd_vapp_href') is None) and
        (status.get('backing', {}).get('status') != 'Missing')):
        logger.info(f"Creating a vcdvapp named: {name} in namespace: {namespace}")

        create_or_instantiate_new_vapp(spec=spec, status=status, name=name, vdc=vdc, logger=logger)

        try:
            # Get the new vApp resource
            vapp_resource = vdc.get_vapp(name)
            vapp = VApp(get_vcd_session().client,
                        resource=vapp_resource)
        except EntityNotFoundException:
            raise kopf.PermanentError(f"Cannot find the newly created vApp {name}")
        _created = True
    else:
        logger.info(f"vApp {name} in namespace: {namespace} alreday exists. Lets reconciliate everything.")
        # The vApp already exists
        try:
            vapp = VApp(get_vcd_session().client,
                        href=status.get('backing').get('vcd_vapp_href'))
            vapp_resource = vapp.get_resource()
        except EntityNotFoundException:
            raise kopf.PermanentError(f"Cannot find the previously created vApp {name}")

    if _created:
        patch.status['backing'] = {
            'vcd_vapp_href': vapp_resource.get('href'),
            'status': VCLOUD_STATUS_MAP[int(vapp_resource.get('status'))],
            'vcd_vdc_href': vdc.href,
            'owner': vapp_resource.Owner.User.get('name'),
            'uuid': vapp_resource.get('id')
        }
        patch.metadata.annotations['managed-by'] = 'kvcd'
        return { 'message': 'vApp successfuly created' }
    else:
        logger.debug(f"Found an existing vapp with the same name: {name}")


def create_or_instantiate_new_vapp(spec: kopf.Spec, status: kopf.Status, name: str, vdc: VDC, logger: kopf.Logger):
    """Create a vcdvapp from specs:
        if catalog and template_name are provided: clone the vApp from the catalog
        else: create the vApp from scratch.

    Args:
        spec (kopf.Spec): Object
        status (kopf.Status): Current status data of the object
        name (str): Name of the object
        vdc (VDC): VDC where the vApp will be created
        logger (kopf.Logger): Logger facility
    """
    try:
        # look for a VM with the same name: if so, just retrun
        vapp_resource = vdc.get_vapp(name)
        return
    except EntityNotFoundException:
        if not spec.get('source_catalog') and not spec.get('source_template_name'):
            logger.debug("Creating a new vApp from scratch")

            # create the vApp
            create_result = vdc.create_vapp(name,
                description=spec.get('description'),
                network=None,
                fence_mode=spec.get('fence_mode', 'bridged'),
                accept_all_eulas=spec.get('accept_all_eulas', True)
            )

            # Monitor the task
            logger.debug(f"Wait for task to complete...")
            task = vcd_session.client.get_task_monitor().wait_for_status(task=create_result.Tasks.Task[0])
            if task.get('status') != TaskStatus.SUCCESS.value:
                raise kopf.PermanentError(f"Failed to create vApp: {task.get('status')}")
        else:
            if not spec.get('source_catalog'):
                raise kopf.PermanentError(f"Missing catalog information to create the vApp {name}")
            if not spec.get('source_template_name'):
                raise kopf.PermanentError(f"Missing template_name information to create the vApp {name}")
            logger.debug(
                f"Instantiating a vApp from a catalog item: {spec.get('source_catalog')} on {spec.get('source_template_name')}"
            )

            # create the vApp
            create_result = vdc.instantiate_vapp(
                name=name,
                catalog=spec.get('source_catalog'),
                template=spec.get('source_template_name'),
                description=spec.get('description'),
                deploy=True,
                power_on=spec.get('powered_on'),
                accept_all_eulas=spec.get('accept_all_eulas'))

        # Monitor the task
        logger.debug(f"Wait for task to complete...")
        task = vcd_session.client.get_task_monitor().wait_for_status(task=create_result.Tasks.Task[0])
        if task.get('status') != TaskStatus.SUCCESS.value:
            raise kopf.PermanentError(f"Failed to create vApp: {task.get('status')}")


@kopf.on.delete('kvcd.lrivallain.dev', 'v1', 'vcdvapps')
def delete_vcdvapp(spec: kopf.Spec, status: kopf.Status, name: str,
    namespace: str, logger: kopf.Logger, patch: kopf.Patch,
    **kwargs):
    """Delete a vcdvapp from specs

    Args:
        spec (kopf.Spec): Object specs
        status (kopf.Status): Current status data of the object
        name (str): Name of the object
        namespace (str): Name of the namespace where object is declared
        logger (kopf.Logger): Logger facility
        patch (kopf.Patch): Patch to apply
    """
    logger.info(f"Deleting a vcdvapp named: {name} in namespace: {namespace}")

    if not status.get('backing') or not status.get('backing', {}).get('vcd_vapp_href'):
        logger.info(f"Skipping deletion: no vApp href found.")
        return # never created vApp
    try:
        if not status.get('backing', {}).get('vcd_vapp_href'):
            raise EntityNotFoundException()
        vapp = VApp(get_vcd_session().client,
                    href=status.get('backing').get('vcd_vapp_href'))
    except EntityNotFoundException:
        logger.info(f"Skipping deletion: no vApp found with href: {status.get('backing').get('vcd_vapp_href')}")
        return  # already deleted vApp?
    if vapp:
        # delete the vApp
        vdc = get_vdc(vcd_session=get_vcd_session(),
                      org_name=spec.get('org'),
                      vdc_name=spec.get('vdc'))
        logger.info(f"Deleting vApp: {name}")
        action_result = vdc.delete_vapp(name, force=spec.get('force_delete', False))
        logger.debug(f"Wait for task to complete...")
        try:
            task = get_vcd_session().client.get_task_monitor().wait_for_status(task=action_result)
            if task.get('status') != TaskStatus.SUCCESS.value:
                raise kopf.PermanentError(f"Failed to delete vApp: {task.get('status')}")
        except BadRequestException:
            raise kopf.TemporaryError(f"The vApp cannot be deleted. Ensure it is power_off to help the process.")
        except Exception as e:
            raise e
        logger.info(f"vApp {name} deleted")
        return {'message': 'vApp successfuly deleted'}


@kopf.on.field('kvcd.lrivallain.dev', 'v1', 'vcdvapps', field='spec.description')
def update_vcdvapp_description(old: dict, new: dict, status: kopf.Status,
                               name: str, namespace: str, logger: kopf.Logger, **kwargs):
    """Update a vcdvapp description

    Args:
        old (dict): Old object specs
        new (dict): New object specs
        status (kopf.Status): Current status data of the object
        name (str): Name of the object
        namespace (str): Name of the namespace where object is declared
        logger (kopf.Logger): Logger facility
    """
    logger.info(f"Updating a vcdvapp description for: {name} in namespace: {namespace}")
    if not status.get('backing', {}).get('vcd_vapp_href'): return
    return vapp_edit_name_and_description(
        vapp_href=status.get('backing', {}).get('vcd_vapp_href'),
        name=name, description=new,
        logger=logger
    )


def vapp_edit_name_and_description(vapp_href: str, name: str, description: str, logger: kopf.Logger):
    """Edit the name and/or the description of a vApp

    Args:
        vapp_href (str): Href of the vApp to edit
        name (str): New name
        description (str): New description
        logger (kopf.Logger): Logger facility
    """
    try:
        vapp = VApp(get_vcd_session().client, href=vapp_href)
    except EntityNotFoundException:
        raise kopf.PermanentError(f"Cannot find the vApp with href: {vapp_href}")
    action_result = vapp.edit_name_and_description(name=name, description=description)
    task = get_vcd_session().client.get_task_monitor().wait_for_status(
        task=action_result)
    if task.get('status') != TaskStatus.SUCCESS.value:
        raise kopf.PermanentError(f"Failed to update vApp: {task.get('status')}")
    logger.info(f"vApp {name} updated")
    return {'message': 'vApp successfuly updated'}


@kopf.on.field('kvcd.lrivallain.dev', 'v1', 'vcdvapps', field='spec.powered_on')
@kopf.on.field('kvcd.lrivallain.dev', 'v1', 'vcdvapps', field='status.backing.status')
def update_vcdvapp_power_state(old: dict, new: dict, status: kopf.Status, spec: kopf.Spec,
                               name: str, namespace: str, logger: kopf.Logger, **kwargs):
    """Update a vcdvapp power state

    Args:
        old (dict): Old object specs
        new (dict): New object specs
        status (kopf.Status): Current status data of the object
        spec (kopf.Spec): Object specs
        name (str): Name of the object
        namespace (str): Name of the namespace where object is declared
        logger (kopf.Logger): Logger facility
    """
    logger.info(f"Updating a vcdvapp power state for: {name} in namespace: {namespace}")
    if not status.get('backing', {}).get('vcd_vapp_href'): return
    return vapp_reconcile_power_state(
        vapp_href=status.get('backing', {}).get('vcd_vapp_href'),
        current_status=status.get('backing').get('status'),
        expected_power_state=spec.get('powered_on'),
        logger=logger)


def vapp_reconcile_power_state(vapp_href: str, current_status:str, expected_power_state: bool, logger: kopf.Logger):
    """Reconcile the vApp power status with spec.

    Args:
        vapp_href (str): Href of the vApp to edit
        current_status (str): Current status of the vApp
        expected_power_state (bool): Expected power state of the vApp
        logger (kopf.Logger): Logger facility
    """
    logger.debug(f"Starting vapp_reconcile_power_state")
    try:
        vapp = VApp(get_vcd_session().client, href=vapp_href)
        vapp.reload() # just to get the vapp name :/
    except EntityNotFoundException:
        raise kopf.PermanentError(f"Cannot find the vApp with href: {vapp_href}")
    # reconcile the vApp power status with spec
    action_result = None
    if expected_power_state and current_status in ['Deployed', 'Suspended', 'Powered off']:
        action = "on"
        logger.info(f"Powering on vApp: {vapp.name}")
        action_result = vapp.deploy()
    if not expected_power_state and current_status in ['Suspended', 'Powered on']:
        action = "off"
        logger.info(f"Shutting down vApp: {vapp.name}")
        action_result = vapp.undeploy()
    if action_result != None:
        task = get_vcd_session().client.get_task_monitor().wait_for_status(
            task=action_result,
            timeout=60,
            poll_frequency=2,
            fail_on_statuses=None,
            expected_target_statuses=[
                TaskStatus.SUCCESS, TaskStatus.ABORTED, TaskStatus.ERROR,
                TaskStatus.CANCELED
            ],
            callback=None)
        if task.get('status') != TaskStatus.SUCCESS.value:
            raise kopf.PermanentError(f"Failed to power {action} vApp: {task.get('status')}")


@kopf.on.field('kvcd.lrivallain.dev', 'v1', 'vcdvapps', field='spec.owner')
@kopf.on.field('kvcd.lrivallain.dev', 'v1', 'vcdvapps', field='status.backing.owner')
def update_vcdvapp_owner(old: dict, new: dict, status: kopf.Status, spec: kopf.Spec,
                               name: str, namespace: str, logger: kopf.Logger, **kwargs):
    """Update a vcdvapp owner

    Args:
        old (dict): Old object specs
        new (dict): New object specs
        status (kopf.Status): Current status data of the object
        spec (kopf.Spec): Object specs
        name (str): Name of the object
        namespace (str): Name of the namespace where object is declared
        logger (kopf.Logger): Logger facility
    """
    logger.info(f"Updating a vcdvapp owner for: {name} in namespace: {namespace}")
    if not status.get('backing', {}).get('vcd_vapp_href'): return
    return vapp_reconcile_owner(
        vapp_href=status.get('backing', {}).get('vcd_vapp_href'),
        current_owner=status.get('backing').get('owner'),
        expected_owner=spec.get('owner'),
        org_name=spec.get('org'),
        logger=logger)


def vapp_reconcile_owner(vapp_href: str, current_owner: str,
                        expected_owner: str, org_name: str,
                        logger: kopf.Logger):
    """Reconcile the vApp owner with spec.

    Args:
        vapp_href (str): Href of the vApp to edit
        current_owner (str): Current owner of the vApp
        expected_owner (str): Expected owner of the vApp
        org_name (str): Name of the organization
        logger (kopf.Logger): Logger facility
    """
    logger.debug(f"Starting vapp_reconcile_owner")
    if not expected_owner:
        return # no need to change owner
    try:
        vapp = VApp(get_vcd_session().client, href=vapp_href)
    except EntityNotFoundException:
        raise kopf.PermanentError(
            f"Cannot find the vApp with href: {vapp_href}")

    # reconcile the vApp owner with spec
    try:
        org = get_org(vcd_session=get_vcd_session(), org_name=org_name)
        future_owner = org.get_user(expected_owner)
    except EntityNotFoundException:
        raise kopf.TemporaryError(
            f"Cannot find the expected owner as an org user: {expected_owner}")

    vapp.change_owner(future_owner.get('href'))
    logger.debug("Successful owner change")


@kopf.on.field('kvcd.lrivallain.dev', 'v1', 'vcdvapps', field='spec.deploymentLeaseInSeconds')
@kopf.on.field('kvcd.lrivallain.dev', 'v1', 'vcdvapps', field='status.backing.deploymentLeaseInSeconds')
@kopf.on.field('kvcd.lrivallain.dev', 'v1', 'vcdvapps', field='spec.storageLeaseInSeconds')
@kopf.on.field('kvcd.lrivallain.dev', 'v1', 'vcdvapps', field='status.backing.storageLeaseInSeconds')
def update_vcdvapp_lease_info(old: dict, new: dict, status: kopf.Status, spec: kopf.Spec,
                              name: str, namespace: str, logger: kopf.Logger, **kwargs):
    """Update a vcdvapp lease_info

    Args:
        old (dict): Old object specs
        new (dict): New object specs
        status (kopf.Status): Current status data of the object
        spec (kopf.Spec): Object specs
        name (str): Name of the object
        namespace (str): Name of the namespace where object is declared
        logger (kopf.Logger): Logger facility
    """
    logger.info(f"Updating a vcdvapp lease_info for: {name} in namespace: {namespace}")
    if not status.get('backing', {}).get('vcd_vapp_href'): return
    return vapp_reconcile_lease_info(
        vapp_href=status.get('backing', {}).get('vcd_vapp_href'),
        current_deploymentLeaseInSeconds=status.get('backing').get('deploymentLeaseInSeconds'),
        current_storageLeaseInSeconds=status.get('backing').get('storageLeaseInSeconds'),
        expected_deploymentLeaseInSeconds=spec.get('deploymentLeaseInSeconds'),
        expected_storageLeaseInSeconds=spec.get('storageLeaseInSeconds'),
        logger=logger)


def vapp_reconcile_lease_info(vapp_href: str, current_deploymentLeaseInSeconds: int,
    current_storageLeaseInSeconds: int, expected_deploymentLeaseInSeconds: int,
    expected_storageLeaseInSeconds: int, logger: kopf.Logger):
    """Reconcile the vApp lease_info with spec.

    Args:
        vapp_href (str): Href of the vApp to edit
        current_deploymentLeaseInSeconds (int): Current deploymentLease in seconds
        current_storageLeaseInSeconds (int): Current storageLease in seconds
        expected_deploymentLeaseInSeconds (int): Expected deploymentLease in seconds
        expected_storageLeaseInSeconds (int): Expected storageLease in seconds
        logger (kopf.Logger): Logger facility
    """
    logger.debug(f"Starting vapp_reconcile_lease_info")
    # if spec are empty or null, we do not want to change the lease_info
    if expected_deploymentLeaseInSeconds is None:
        expected_deploymentLeaseInSeconds = current_deploymentLeaseInSeconds
    if expected_storageLeaseInSeconds is None:
        expected_storageLeaseInSeconds = current_storageLeaseInSeconds
    if ((expected_deploymentLeaseInSeconds == current_deploymentLeaseInSeconds) and
        (expected_storageLeaseInSeconds == current_storageLeaseInSeconds)):
        return # no need to change lease_info

    try:
        vapp = VApp(get_vcd_session().client, href=vapp_href)
    except EntityNotFoundException:
        raise kopf.PermanentError(
            f"Cannot find the vApp with href: {vapp_href}")

    try:
        vapp.set_lease(
            deployment_lease=expected_deploymentLeaseInSeconds,
            storage_lease=expected_storageLeaseInSeconds
        )
    except BadRequestException as e:
        if e.vcd_error.get('minorErrorCode') == 'BUSY_ENTITY':
            raise kopf.TemporaryError(f"Cannot set lease for vApp: {vapp_href}")
        else:
            raise e
    except Exception as e:
        raise e
    logger.debug("Successful lease_info change")


@kopf.on.field('kvcd.lrivallain.dev', 'v1', 'vcdvapps', field='metadata.annotations')
@kopf.on.field('kvcd.lrivallain.dev', 'v1', 'vcdvapps', field='status.backing.metadata')
def update_vcdvapp_metadata(old: dict, new: dict, status: kopf.Status,
                            annotations: kopf._cogs.structs.dicts.MappingView,
                            name: str, namespace: str, logger: kopf.Logger,
                            **kwargs):
    """Update a vcdvapp metadata entries

    Args:
        old (dict): Old object specs
        new (dict): New object specs
        status (kopf.Status): Current status data of the object
        annotations (dict): Object annotations
        name (str): Name of the object
        namespace (str): Name of the namespace where object is declared
        logger (kopf.Logger): Logger facility
    """
    logger.info(f"Updating a vcdvapp metadata entries for: {name} in namespace: {namespace}")
    if not status.get('backing', {}).get('vcd_vapp_href'): return
    return vapp_reconcile_metadata(
        vapp_href=status.get('backing', {}).get('vcd_vapp_href'),
        current_metadata=status.get('backing').get('metadata', {}),
        expected_metadata=annotations,
        logger=logger)



def vapp_reconcile_metadata(vapp_href: str, current_metadata: kopf._cogs.structs.dicts.MappingView,
    expected_metadata: dict, logger: kopf.Logger):
    """Reconcile the vApp metadata entries with spec.

    Args:
        vapp_href (str): Href of the vApp to edit
        current_metadata (dict): Current deploymentLease in seconds
        expected_metadata (kopf._cogs.structs.dicts.MappingView): Current storageLease in seconds
        logger (kopf.Logger): Logger facility
    """
    logger.debug(f"Starting vapp_reconcile_metadata")
    try:
        vapp = VApp(get_vcd_session().client, href=vapp_href)
        vapp.reload()  # just to get the vapp name :/
    except EntityNotFoundException:
        raise kopf.PermanentError(
            f"Cannot find the vApp with href: {vapp_href}")

    # Sadly we cannot set READONLY metadata except if we are running as sysadmin
    if get_vcd_session().client.is_sysadmin():
        metadata_visibility = MetadataVisibility.READONLY.value
    else:
        metadata_visibility = MetadataVisibility.READ_WRITE.value
    for entry in expected_metadata:
        if not entry.startswith('kopf.'): # and not entry.startswith('kubectl.'):
            if (entry not in current_metadata) or (expected_metadata[entry] != current_metadata[entry]):
                try:
                    task = vapp.set_metadata(
                        domain=MetadataDomain.GENERAL.value,
                        visibility=metadata_visibility,
                        key=entry,
                        value=str(expected_metadata[entry]))
                    result = get_vcd_session().client.get_task_monitor().wait_for_status(task=task)
                    if result.get('status') != TaskStatus.SUCCESS.value:
                        raise kopf.PermanentError(f"Failed to create metadata on vApp: {result.get('status')}")
                except OperationNotSupportedException as e:
                    raise kopf.TemporaryError(f"OperationNotSupportedException exception raised by vCloud")
                except Exception as e:
                    raise e
                logger.debug(f"Successful metadata change for: {entry} on vApp {vapp.name}")


@kopf.timer('kvcd.lrivallain.dev', 'v1', 'vcdvapps',
            interval=kvcd_config.refresh_interval,
            initial_delay=kvcd_config.refresh_initial_delay,
            idle=kvcd_config.refresh_idle_delay)
async def refresh_vcdvapp(spec: kopf.Spec, status: kopf.Status, name: str, namespace: str,
    annotations: kopf._cogs.structs.dicts.MappingView, logger: kopf.Logger,
    patch: kopf.Patch, **kwargs):
    """Refresh a vcdvapp from its backing state

    Args:
        spec (kopf.Spec): Object specs
        status (kopf.Status): Current status data of the object
        name (str): Name of the object
        namespace (str): Name of the namespace where object is declared
        annotations (kopf._cogs.structs.dicts.MappingView): Object annotations
        logger (kopf.Logger): Logger facility
        patch (kopf.Patch): Patch to apply
    """
    if not status.get('backing', {}).get('vcd_vapp_href'):
        return  # nothing to update
    logger.debug(f"Timer: update status of vApp: {name} in namespace: {namespace}")
    vdc = get_vdc(vcd_session=get_vcd_session(),
                  org_name=spec.get('org'),
                  vdc_name=spec.get('vdc'))

    # look for a vApp with the same name
    try:
        vapp_resource = vdc.get_vapp(name)
        vapp = VApp(get_vcd_session().client, resource=vapp_resource)
        vapp.reload()
    except EntityNotFoundException:
        logger.error(f"vApp {name} is not existing anymore on vCloud")
        # removing backing data
        backing_info = {
            'vcd_vapp_href': None,
            'status': 'Missing',
            'uuid': None
        }
        patch.status['backing'] = backing_info
        raise kopf.PermanentError(f"vApp {name} is not existing anymore on vCloud")

    backing_update = {}
    # leases
    lease_info = vapp.get_lease()
    if lease_info.get('StorageLeaseExpiration'):
        # compare current utc to the iso date in StorageLeaseExpiration to know if it is expired
        if dateutil.parser.isoparse(str(lease_info.get('StorageLeaseExpiration'))) < datetime.now(timezone.utc):
            backing_update['status'] = "Expired"
    for l in ['DeploymentLeaseInSeconds', 'StorageLeaseInSeconds']:
        lease_value = int(lease_info.get(l))
        lease_key = lowercase_first_string_letter(l)
        backing_update[lease_key] = lease_value
    if backing_update.get('status') != "Expired":
        # vApp status
        backing_status = VCLOUD_STATUS_MAP[int(vapp_resource.get('status'))]
        backing_update['status'] = backing_status
        # Metadata
        backing_update['metadata'] = metadata_to_dict(vapp.get_metadata())
        # vApp owner
        backing_owner = vapp.resource.Owner.User.get('name')
        backing_update['owner'] = backing_owner
    # Update the backing status
    patch.status['backing'] = backing_update
    # Force the managed-by metadata on vCloud side
    if not annotations.get('managed-by'):
        patch.metadata.annotations['managed-by'] = 'kvcd'
    return
