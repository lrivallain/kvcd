"""Set of helpers to manage a Cloud Director connection and its related objects.
"""

import atexit
import ssl
import sys
import logging
from enum import Enum

# Extra packages
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client as vCDClient
from pyvcloud.vcd.client import EntityType
from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.client import ResourceType
from pyvcloud.vcd.client import MetadataDomain
from pyvcloud.vcd.client import MetadataValueType
from pyvcloud.vcd.client import MetadataVisibility
from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
from pyvcloud.vcd.vm import VM
import requests
from lxml.objectify import ObjectifiedElement


logger = logging.getLogger(__name__)


class VcdSession:
    """Define VcdSession class to manage the Cloud Director connection and its related objects.
    """

    def __init__(self,
                 hostname: str,
                 username: str,
                 password: str,
                 organisation: str,
                 port: int = 443,
                 verify_ssl: bool = True):
        """Define VcdSession class based on input parameters

        Args:
            hostname (str): Hostname of the vCloud instance
            username (str): Username to use
            password (str): User's password
            organisation (str): Name of the organisation
            verify_ssl (bool, optional): Verify the vCloud SSL certificate. Defaults to True.

        Raises:
            VCDError: Any vCloud director related error.
        """
        logger.info(f'Initializing a Cloud Director session to {hostname} in organisation {organisation}')
        self._creds = BasicLoginCredentials(username, organisation, password)
        try:
            self.client = vCDClient(uri=f"https://{hostname}:{port}",
                                    verify_ssl_certs=verify_ssl,
                                    log_file=None,
                                    log_requests=False,
                                    log_headers=False,
                                    log_bodies=False)
            self.client.set_credentials(self._creds)
            atexit.register(self.__close)
        except Exception as err:
            raise VCDError(f'Unable to create the Cloud Director session: {err}')
        # shortcuts to usefull settings
        self.hostname = hostname
        self.org = Org(self.client,
                       resource=self.client.get_org())
        logger.debug(f'Connected to {self.client.get_api_uri()})')


    def rehydrate(self):
        """Renew the authentication, based on stored credentials.
        """
        self.client.set_credentials(self._creds)


    def __close(self):
        """Exit method to cloture a connection
        """
        logger.info("Closing the Cloud Director session")
        self.client.logout()
        logger.debug("Cloud Director session closed")



class VCDError(Exception):
    """Base class for exceptions with logging.
    """
    def __init__(self, msg='', *args,**kwargs):
        logger.error(f"VCDError: {msg}")
        sys.exit(msg)

    def __str__(self):
        return self.msg


def get_org(vcd_session:VcdSession, org_name: str):
    """Get an Org VDC based on its name

    Args:
        vcd_session (VcdSession): VCD session
        org_name (str): Name of the Organization

    Returns:
        Org: Org object
    """
    try:
        org_resource = vcd_session.client.get_org_by_name(org_name)
    except EntityNotFoundException:
        raise kopf.PermanentError(f"No Org found with name: {org_name}")
    org = Org(vcd_session.client, resource=org_resource)
    logger.debug(f"Org found: {org_resource.get('name')}")
    return org


def get_vdc(vcd_session: VcdSession, org_name: str, vdc_name: str):
    """Get an Org VDC based on its name

    Args:
        vcd_session (VcdSession): VCD session
        org_name (str): Name of the Organization
        vdc_name (str): Name of the VDC to get

    Returns:
        VDC: VDC object
    """
    org = get_org(vcd_session=vcd_session, org_name=org_name)
    vdc_resource = org.get_vdc(vdc_name)
    if vdc_resource == None:  # Compare to None as record.__repr()__ return an empty str: ''
        raise kopf.PermanentError(f"No Org VDC found with name: {vdc_name}")
    vdc = VDC(vcd_session.client, resource=vdc_resource)
    logger.debug(f"Org VDC found: {vdc_resource.get('name')}")
    return vdc