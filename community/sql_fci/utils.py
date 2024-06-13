# Copyright 2017 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Helper functions used throughout the template files.

Some things need to stay consistent across the template files, mostly
names of resources. These need to be consistent because they are used to
generate references.

the python module "ipaddress" already handles what these functions do, but
third-party python modules aren't allowed to be imported:

https://cloud.google.com/deployment-manager/docs/configuration/templates/import-python-libraries

"""

# CIDR used by the cluster nodes and the load balancer.
DEFAULT_DEPLOYMENT_CIDR = "10.129.0.0/24"

# extra constants defining fields required to define a scratch disk
DISK_INTERFACE = "interface"
DISK_MODE = "mode"
SSD_DISK_INTERFACE = "SCSI"
SSD_DISK_MODE = "READ_WRITE"
SSD_DISK_TYPE = "SCRATCH"

# These could be potentially configurable by the user in the future, however
# right now these are the only values tested, and making the ports not
# configurable keeps clutter off of the cloud launcher.
HEALTH_CHECK_PORT = 1818
APPLICATION_PORT = 1433

# somewhat arbitrary. We just want a sensible maximum number of IPs to allocate
# on the subnet, and it can't overlap with the reserved IP numbers below or
# go over the maximum amount of IPs in a byte.
_MAX_IP_NODE_NUMBER = 198
_MIN_IP_NUMBER = 2

# we need to offset the IPs by 2 to leave one IP for the subnet (a.b.c.0) and
# one IP for the gateway (a.b.c.1)
_IP_NODE_NUMBER_OFFSET = 2

# Maximum name length for VMs. Active directory has a requirement that the name
# lengths be less than 15 characters.
_MAX_NAME_LEN = 14


# Ip address numbers for specific purposes. This assumes that there will be
# less than 199 nodes in the cluster.
_AD_NODE_IP_SUFFIX = _MAX_IP_NODE_NUMBER + 1
_CLUSTER_IP_SUFFIX = _AD_NODE_IP_SUFFIX + 1
_APPLICATION_IP_SUFFIX = _CLUSTER_IP_SUFFIX + 1
_MAX_IP_NUMBER = _APPLICATION_IP_SUFFIX


_RTC_ENDPOINT = "https://runtimeconfig.googleapis.com/v1beta1"

AD_NODE_NAME = "ad"

_NET_NAME = "net"
_SUB_NAME = "sub"

# These endpoints make unique runtimeconfig URLs, config names, and waiter
# names unique. Each of these endpoints should have a 1:1 correspondence with a
# "phase" in the deployment.
CREATE_DOMAIN_URL_ENDPOINT = "create_domain"
JOIN_DOMAIN_URL_ENDPOINT = "join_domain"
CREATE_CLUSTER_URL_ENDPOINT = "cluster"
INSTALL_FCI_URL_ENDPOINT = "fci"

# Microsoft AD node names are not allowed to have the following characters
_INVALID_NAME_CHARS = set(":*?\"<>|\\/")

_REGION_TO_ZONES = {
    "northamerica-northeast1": ["a", "b", "c"],
    "southamerica-east1": ["a", "b", "c"],
    "australia-southeast1": ["a", "b", "c"],
    "asia-south1": ["a", "b", "c"],
    "asia-northeast1": ["a", "b", "c"],
    "asia-southeast1": ["a", "b"],
    "asia-east1": ["a", "b", "c"],
    "europe-west2": ["a", "b", "c"],
    "europe-west3": ["a", "b", "c"],
    "europe-west1": ["d", "b", "c"],
    "europe-west4": ["b", "c"],
    "us-west1": ["a", "b", "c"],
    "us-central1": ["a", "b", "c", "f"],
    "us-east1": ["d", "b", "c"],
    "us-east4": ["a", "b", "c"],
}


class IPv4CidrValidationError(Exception):
  """Raised when a CIDR is not valid."""


class IPv4OutOfRangeError(Exception):
  """Raised when an IP is out of the accepted range."""


class VmInputValidationError(Exception):
  """Raised when some VM config is invalid."""


def _GetZoneFromRegion(region, zone_number):
  return "{region}-{zone}".format(
      region=region, zone=_REGION_TO_ZONES[region][zone_number])


def ConvertVolumeSizeString(volume_size_gb):
  """Converts the volume size defined in the schema to an int."""
  volume_sizes = {
      "500 GB (128 GB PD SSD x 4)": 500,
      "1000 GB (256 GB PD SSD x 4)": 1000,
  }
  return volume_sizes[volume_size_gb]


def ConvertMachineTypeString(machine_type):
  """Converts a machine type defined in the schema to a GCE compatible form."""
  machine_types = {
      "4 vCPUs, 15 GB Memory": "n1-standard-4",
      "8 vCPUs, 30 GB Memory": "n1-standard-8"
  }
  return machine_types[machine_type]


def GetDefaultZoneFromRegion(region):
  return _GetZoneFromRegion(region, 0)


def GetNodeZoneFromRegion(region, node_num):
  zones = _REGION_TO_ZONES[region]
  zone_index = node_num % len(zones)
  return _GetZoneFromRegion(region, zone_index)


def GetZoneSet(region, number_of_nodes):
  """Returns the set of zones that will be used with this deployment.

  Args:
    region: The region being used for this deployment
    number_of_nodes: The number of cluster nodes being used in this deployment


  Returns:
    set of zones that will be used in this deployment.
  """
  zones = set()
  for node_index in xrange(number_of_nodes):
    zones.add(GetNodeZoneFromRegion(region, node_index))
  return zones


def NetworkName(deployment):
  """Returns the name of the network based on the deployment.

  Args:
    deployment: the name of this deployment.

  Returns:
    The name of the network.
  """
  return "{}-{}".format(deployment, _NET_NAME)


def SubnetName(deployment):
  """Returns the name of the subnet based on the deployment.

  Args:
    deployment: the name of this deployment.

  Returns:
    The name of the subnet.
  """
  return "{}-{}".format(deployment, _SUB_NAME)


def ValidateNodeName(name):
  """Validates node name.

  Because all nodes will be a part of the Active Directory, the node names have
  to conform to the standards here:

  https://technet.microsoft.com/en-us/library/cc961556.aspx

  Args:
    name: the name of the node.

  Raises:
    VmInputValidationError: if there is a problem with the input
  """

  invalid_chars = _INVALID_NAME_CHARS.intersection(name)
  if invalid_chars:
    raise VmInputValidationError("Node name must not contain any of {invalid}. "
                                 "Please check the deployment name and "
                                 "ensure that it does not contain the {invalid}"
                                 " character".format(invalid=invalid_chars))
  if len(name) > _MAX_NAME_LEN:
    raise VmInputValidationError(
        "Node name is too long. Node names are based on deployment name"
        " and total length must be no longer than {} characters.".format(
            _MAX_NAME_LEN))


def NodeName(deployment, suffix):
  """Returns the name of the node based on the node number.

  Args:
    deployment: the name of this deployment.
    suffix: the number of this node.

  Raises:
    VmInputValidationError: if there is a problem with the input

  Returns:
    The name of the node.
  """
  node_suffix = "-{}".format(suffix)
  deployment = deployment[0:_MAX_NAME_LEN - len(node_suffix)]
  node_name = "{}{}".format(deployment, node_suffix)

  ValidateNodeName(node_name)
  return node_name


def AdNodeName(deployment):
  """Returns the name of the active directory node.

  Args:
    deployment: the name of this deployment.

  Returns:
    The name of the active directory node.
  """
  return NodeName(deployment, AD_NODE_NAME)


def AllNodeNames(deployment, num_vms):
  """Returns a list of all cluster node names, as a string.

  Args:
    deployment: the name of this deployment.
    num_vms: total number of cluster vms in the system.

  Returns:
    A list of all cluster node names, as a string. For example:
    "node-0,node-1,node-2"
  """

  def Name(node_number):
    return NodeName(deployment, node_number)

  return ",".join(Name(node_number) for node_number in xrange(num_vms))


def ConfigName(deployment, name):
  """Returns the name of the config.

  Args:
    deployment: the name of the deployment.
    name: the "tag" used to differentiate this config from others.

  Returns:
    The name of the config.
  """
  return "{}-config-{}".format(deployment, name)


def WaiterName(deployment, name):
  """Returns the name of the waiter.

  Args:
    deployment: the name of the deployment.
    name: the "tag" used to differentiate this waiter from others.

  Returns:
    The name of the waiter.
  """
  return "{}-waiter-{}".format(deployment, name)


def ConfigURL(deployment, project, name):
  """Returns the URL that this config will use.

  Args:
    deployment: the name of the deployment.
    project: the project used to deploy this config.
    name: the "tag" used to differentiate this config from others.

  Returns:
    The name of the waiter.
  """
  return "{}/projects/{}/configs/{}".format(
      _RTC_ENDPOINT, project, ConfigName(deployment, name))


def ValidateIPv4Cidr(cidr):
  """Raises an error if the string provided is not a valid cidr.

  There are two alternative approaches to having this function, both have
  problems:
  1) just use the python "ipaddress" module, which has IP validation built in
     already. The problem with that is that the deployment manager (the system
     that will be executing this code) will not have access to that module.
  2) have an IPv4 CIDR regex, which are readily available through a Google
     search. The problem with this approach is that the regex is hard to
     understand and you can not fail with fine grained error messages.

  We also have slightly more strict requirements than just making sure the
  cidr is valid: we want the subnet length to rest on a byte, and we want the
  unused bytes in the cidr to be '0'. These extra requirements makes
  IP manipulation/building easier.

  Args:
    cidr: standard cidr, as a string. For example 10.0.2.0/24

  Raises:
    IPv4CidrValidationError: if the cidr string is not in standard cidr
                             notation.
    ValueError: if the cidr does not have a subnet length.
  """

  # Cidrs need to be an IP, followed by a '/', followed by a subnet length
  ip_with_subnet_length = cidr.split("/")
  if len(ip_with_subnet_length) != 2:
    raise ValueError("missing subnet length from cidr")

  # The subnet length must be an 8, 16, or 24
  subnet_length = ip_with_subnet_length[1]
  if subnet_length != "8" and subnet_length != "16" and subnet_length != "24":
    raise IPv4CidrValidationError("subnet length must be either 8, 16, or 24.")

  # The IP needs to have 4 segments
  ip_segments = ip_with_subnet_length[0].split(".")
  if len(ip_segments) != 4:
    raise IPv4CidrValidationError("the ip in the cidr must have 4 segments "
                                  "separated by a '.' character.")

  # The 4 IP segments need to be in base 10 and be between 0 and 255, inclusive.
  for segment in ip_segments:
    try:
      segment_val = int(segment)
      if segment_val < 0 or segment_val > 255:
        raise IPv4CidrValidationError("ip segments must be between 0 and 255"
                                      "(inclusive)")

    except ValueError:
      raise IPv4CidrValidationError("ip segments must be base 10 integers.")

  # If the subnet length is 8, then the last 3 bytes of the IP must be 0
  if subnet_length == "8" and (ip_segments[1] != "0" or
                               ip_segments[2] != "0" or
                               ip_segments[3] != "0"):
    raise IPv4CidrValidationError("if the subnet length is 8, then the "
                                  "second, third and fourth bytes must be 0.")

  # If the subnet length is 16, then the last 2 bytes of the IP must be 0
  if subnet_length == "16" and (ip_segments[2] != "0" or
                                ip_segments[3] != "0"):
    raise IPv4CidrValidationError("if the subnet length is 16, then the "
                                  "third and fourth bytes must be 0.")

  # If the subnet length is 24, then the last byte of the IP must be 0
  if subnet_length == "24" and ip_segments[3] != "0":
    raise IPv4CidrValidationError("if the subnet length is 24, then the "
                                  "fourth byte must be 0.")


def GetIp(cidr, ip_number):
  """Gets the IP in the cidr that corresponds to ip_number.

  Args:
    cidr: string representing the cidr in a.b.c.d/x form.
    ip_number: number of the IP.

  Raises:
    IPv4OutOfRangeError: the ip_number is not within the acceptable range.

  Returns:
    the IP address that corresponds to ip_number. For example, if cidr is
    10.0.0.0/24, and num is 1, returns 10.0.0.1
  """
  ValidateIPv4Cidr(cidr)

  if ip_number < _MIN_IP_NUMBER or ip_number > _MAX_IP_NUMBER:
    raise IPv4OutOfRangeError("ip number needs to be between {} and {}".format(
        _MIN_IP_NUMBER, _MAX_IP_NUMBER))

  base = cidr.split("/")[0].split(".")
  base[-1] = str(ip_number)
  return ".".join(base)


def NodeIp(cidr, node_number):
  """Returns the IP to be used by a node VM, as a string.

  We add 2 because 0 is reserved for the subnet address and 1 is reserved
  for the gateway. so node-0 gets ip of x.y.z.2, node-1 gets x.y.z.3, etc

  Args:
    cidr: string representing the cidr in a.b.c.d/x form.
    node_number: number of the node VM.

  Raises:
    IPv4OutOfRangeError: The node IP number is not within the valid range

  Returns:
    The IP to be used by a node VM, as a string
  """

  ip_number = node_number + _IP_NODE_NUMBER_OFFSET

  if ip_number > _MAX_IP_NODE_NUMBER:
    raise IPv4OutOfRangeError("ip number needs to be between {} and {}".format(
        _MIN_IP_NUMBER, _MAX_IP_NODE_NUMBER))

  return GetIp(cidr, ip_number)


def AdNodeIp(cidr):
  """Returns the IP to be used by the AD VM, as a string.

  Args:
    cidr: string representing the cidr in a.b.c.d/x form.

  Returns:
    The IP to be used by the AD VM, as a string.
  """
  return GetIp(cidr, _AD_NODE_IP_SUFFIX)


def ClusterIp(cidr):
  """Returns the IP to be used by the backend cluster.

  Args:
    cidr: string representing the cidr in a.b.c.d/x form.

  Returns:
    The IP to be used by the backend cluster.
  """
  return GetIp(cidr, _CLUSTER_IP_SUFFIX)


def ApplicationIp(cidr):
  """Returns the IP to be used by the SQL server.

  Requests to SQL server from the clients will use this IP.

  Args:
    cidr: string representing the cidr in a.b.c.d/x form.

  Returns:
    The IP to be used by the SQL server.
  """
  return GetIp(cidr, _APPLICATION_IP_SUFFIX)


def InstanceGroupName(deployment, zone):
  """Returns the name of the instance group.

  A consistent name is required to define references and dependencies.
  Assumes that only one instance group will be used for the entire deployment.

  Args:
    deployment: the name of this deployment.
    zone: the zone for this particular instance group

  Returns:
    The name of the instance group.
  """
  return "{}-instance-group-{}".format(deployment, zone)


def HealthCheckName(deployment):
  """Returns the name of the health check.

  A consistent name is required to define references and dependencies.
  Assumes that only one health check will be used for the entire deployment.

  Args:
    deployment: the name of this deployment.

  Returns:
    The name of the health check.
  """
  return "{}-health-check".format(deployment)
