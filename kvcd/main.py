"""This module is the one to run with `kopf run` command to start the operator.

Warning: It contains a global named `get_vcd_session`, populated after the project is started.
This is probably something to cleanup in the future.
"""

import kopf
import time
import logging
import time
from dotenv import load_dotenv, find_dotenv
from kvcd.vmware.vcloud_helper import VcdSession
from kvcd.utils import setInterval
from kvcd.config import KvcdConfig


logger = logging.getLogger(__name__)


vcd_session = None
def get_vcd_session():
    """Return the current version of `vcd_session`

    Returns:
        VcdSession: current version of `vcd_session`
    """
    return vcd_session


# load dotenv file
try:
    load_dotenv(find_dotenv(raise_error_if_not_found=True, usecwd=True))
    logger.info("Configuration loaded from .env file")
except IOError:
    # Assume that the configuration is already loaded in current env.
    pass
# parse configuration from env
kvcd_config = KvcdConfig.from_environ()
logger.info("Configuration is loaded")


@kopf.on.startup()
def startup_kvcd(logger, **kwargs):
    """Startup function: create the vCD session
    """
    refresh_vcdsession()
    logger.info("vCD session is now ready")


@setInterval(sec=kvcd_config.vcd.refresh_session_interval)
def refresh_vcdsession():
    """Refresh the vCD session

    This function is run on a regular basis to update `vcd_session` with
    a working pyvcloud client.
    """
    # create the vcd session
    global vcd_session
    if isinstance(vcd_session, VcdSession):
        logger.debug("Refreshing the vCD session")
        vcd_session.rehydrate()
    else:
        logger.debug("Creating a fresh new vCD session")
        vcd_session = VcdSession(
            hostname=kvcd_config.vcd.host,
            port=kvcd_config.vcd.port,
            username=kvcd_config.vcd.username,
            password=kvcd_config.vcd.password,
            organisation=kvcd_config.vcd.org,
            verify_ssl=kvcd_config.vcd.verify_ssl,
        )


# Import the resources management functions
from kvcd.vmware.vcloud_vapp import create_vcdvapp
from kvcd.vmware.vcloud_vapp import delete_vcdvapp
from kvcd.vmware.vcloud_vapp import update_vcdvapp_description
from kvcd.vmware.vcloud_vapp import update_vcdvapp_power_state
from kvcd.vmware.vcloud_vapp import update_vcdvapp_owner
from kvcd.vmware.vcloud_vapp import update_vcdvapp_lease_info
from kvcd.vmware.vcloud_vapp import update_vcdvapp_metadata
from kvcd.vmware.vcloud_vapp import refresh_vcdvapp