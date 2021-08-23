"""This Submodules contains the definition of the expected configuration
to setup to use kvcd.

The main configuration is handled by `environ-config` module.
"""

import environ
import logging

logger = logging.getLogger(__name__)

@environ.config(prefix="KVCD")
class KvcdConfig:
    """kvcd configuration
    """
    @environ.config
    class VcloudConfig:
        """vcloud configuration
        """
        host = environ.var(
            help="Hostname of the vCloud instance")
        port = environ.var(
            default=443,
            help="Port of the vCloud instance",
            converter=int)
        org = environ.var(
            default="System",
            help="Organization of the vCloud instance")
        username = environ.var(
            default="Administrator",
            help="Username of the vCloud instance")
        password = environ.var(
            help="Password of the vCloud instance user")
        verify_ssl = environ.bool_var(
            default=True,
            help="Verify SSL certificate of the vCloud instance")
        refresh_session_interval = environ.var(
            default=3600,
            help="Interval (in secs) between to refresh of the authentication session",
            converter=int)

    vcd = environ.group(
        VcloudConfig,
        optional=False)
    refresh_interval = environ.var(
        default=60,
        help="Refresh interval of the vCloud instance data for each object",
        converter=int)
    refresh_initial_delay = environ.var(
        default=60,
        help="Warming up duration",
        converter=int)
    refresh_idle_delay = environ.var(
        default=60,
        help="Reduce the number of timer checks when the ressource is changed",
        converter=int)
