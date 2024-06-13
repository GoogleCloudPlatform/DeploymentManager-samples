# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Generates a config defining the VMs in the gcloud deployment.

This file is not meant to be used in general, and instead is written to
interract with google's cloud deployment manager system. The key function in
this file is "GenerateConfig", which the deployment manager will call to get
the list of resources it must deploy.

Without the context of google's deployment manager system, this file will
probably not make any sense. Please see:

https://cloud.google.com/deployment-manager/docs/

for the necessary background.
"""

import common
import default
import utils


# number of cluster node requirements here:
# https://docs.microsoft.com/en-us/windows-server/storage/storage-spaces/storage-spaces-direct-hardware-requirements
_MIN_CLUSTER_NODES = 2
_MAX_CLUSTER_NODES = 3
_MIN_DISKS = 4
# Nodes need their hostname to be less than 15 or else AD will not be
# able to distinguish between them
_MAX_NAME_LEN = 14

_PD_DISK = "pd-standard"
_PD_SSD_DISK = "pd-ssd"
_SSD_DISK = "local-ssd"

_NUM_PD_SSD_DISKS = 4

# There is about a 2GB overhead per disk for S2D deployments
_S2D_OVERHEAD = 2

# At this point, we don't want the user to be able to configue any number.
# This keeps the testing area down.
_VALID_VOLUME_SIZES = (500, 1000)

# Assumes 4 disks. Take the closest power of two that is larger than the volume.
_VOLUME_TO_DISK_SIZE = {
    500: 128,
    1000: 256
}

# Indicates that the VMs associated with this template are SQL FCI VMs. Used
# only for telemetry purposes.
_SQL_FCI_TAG = "SQLFCI"

# The current set of supported images
_SQL_SVR_2016 = "sql-fci-2016-v20180213"
_WINDOWS_2016 = "sql-fci-ad-2016-v20180213"

_SQL_FCI_PUBLIC_FAMILY = "sql-fci-public"


def DiskName(vm_name, disk_type, disk_number):
  """Returns the name of this disk.

  Args:
    vm_name: The name of the vm this disk will be attached to.
    disk_type: The type of the disk.
    disk_number: The number of this disk. Must be unique on the VM.

  Returns:
    The name of the disk.
  """
  return "{}-disk-{}-{}".format(vm_name, disk_type, disk_number)


def DiskType(project, zone, disk_type_str):
  """Returns the full path of the disk type.

  Args:
    project: the project of this deployment.
    zone: The zone the disk will be deployed in.
    disk_type_str: The name of the disk type.

  Returns:
    The full path of the disk type.
  """
  return "{}projects/{}/zones/{}/diskTypes/{}".format(
      default.COMPUTE_URL_BASE, project, zone, disk_type_str)


def Disk(project, zone, vm_name, disk_type, disk_num, size_gb):
  """Generates a top level disk.

  resource that gets created at the top level, as opposed
  to a resource that is embedded within a VM definition.

  Args:
    project: The owner project that is deploying this template.
    zone: The zone that this disk will be deployed in.
    vm_name: the name of the VM that will use this disk.
    disk_type: the type of disk (PD, SSD, PD-SSD)
    disk_num: the number of the disk, making it unique to the VM.

    size_gb: the size of the disk in GB.
  Returns:
    A top level disk resource definition.
  """
  return {
      default.NAME: DiskName(vm_name, disk_type, disk_num),
      default.TYPE: default.DISK,
      default.PROPERTIES: {
          default.ZONE: zone,
          default.SIZE_GB: size_gb,
          default.TYPE: DiskType(project, zone, disk_type)
      }
  }


def SSDDisk(vm_name, disk_num, project, zone):
  """Returns an SSD disk configuration.

  The definition is not top-level, and should be embedded within a disk
  definition.

  Args:
    vm_name: name of the VM that this disk will be on.
    disk_num: the number for this disk. Must correspond to the top-level disk.
    project: the project that is deploying the VM.
    zone: the zone where this disk will be deployed.

  Returns:
    A vm SSD disk configuration.
  """
  disk_name = DiskName(vm_name, _SSD_DISK, disk_num)
  return {
      default.DEVICE_NAME: disk_name,
      default.TYPE: utils.SSD_DISK_TYPE,
      utils.DISK_INTERFACE: utils.SSD_DISK_INTERFACE,
      utils.DISK_MODE: utils.SSD_DISK_MODE,
      default.AUTO_DELETE: True,
      default.INITIALIZEP: {
          default.DISKTYPE: DiskType(project, zone, _SSD_DISK),
      }
  }


def VmDisk(vm_name, disk_type, disk_num):
  """Returns a vm disk definition.

  The definition is not top-level, and should be embedded within a disk
  definition.

  Args:
    vm_name: name of the VM that this disk will be on.
    disk_type: type of the disk.
    disk_num: the number for this disk. Must correspond to the top-level disk.

  Returns:
    A vm disk definition.
  """
  disk_name = DiskName(vm_name, disk_type, disk_num)
  return {
      default.DEVICE_NAME: disk_name,
      default.DISK_SOURCE: common.Ref(disk_name),
      default.AUTO_DELETE: True
  }


def BootDisk(base_name, device_name, project, zone, image):
  """Returns a boot disk definition.

  This disk is necessary for all VMs, and will be less configurable by the user.

  Args:
    base_name: name that the VM is based off of.
    device_name: name of this disk.
    project: the project that is deploying the VM.
    zone: the zone where this disk will be deployed.
    image: the full path to the image used for booting.

  Returns:
    A boot disk definition.
  """
  return {
      default.DEVICE_NAME: device_name,
      default.AUTO_DELETE: True,
      default.BOOT: True,
      default.INITIALIZEP: {
          default.DISK_NAME: "{}-disk".format(base_name),
          default.DISKTYPE: DiskType(project, zone, _PD_SSD_DISK),
          default.SRCIMAGE: image,
          default.DISK_SIZE: 100
      }
  }


def BuildClusterInstanceMetadata(context, zone, node_number):
  """Returns a list of key/value pairs for the cluster instance metadata.

  Args:
    context: The context of the deployment.
    zone: The zone where the VM will reside.
    node_number: The unique number of this cluster VM.

  Returns:
    A list of key value pairs specific to the cluster instance nodes.
  """
  deployment = context.env["deployment"]
  project = context.env["project"]
  sql_cidr = context.properties.get("sql_cidr", utils.DEFAULT_DEPLOYMENT_CIDR)
  service_account = context.properties["service_account"]
  num_cluster_nodes = context.properties["num_cluster_nodes"]
  is_test = context.properties.get("dev_mode", "false")
  volume_size_gb = context.properties["volume_size_gb"]

  return {
      "items": [
          {
              "key":
                  "sysprep-specialize-script-ps1",
              "value": ("Install-WindowsFeature -Name File-Services, "
                        "Failover-Clustering -IncludeManagementTools")
          },
          {
              "key": "enable-wsfc",
              "value": "true"
          },
          {
              "key": "wsfc-agent-port",
              "value": utils.HEALTH_CHECK_PORT
          },
          {
              "key": "windows-startup-script-ps1",
              "value": context.imports["install.ps1"]
          },
          {
              "key":
                  "create-domain-config-url",
              "value":
                  utils.ConfigURL(deployment, project,
                                  utils.CREATE_DOMAIN_URL_ENDPOINT)
          },
          {
              "key":
                  "join-domain-config-url",
              "value":
                  utils.ConfigURL(deployment, project,
                                  utils.JOIN_DOMAIN_URL_ENDPOINT)
          },
          {
              "key":
                  "create-cluster-config-url",
              "value":
                  utils.ConfigURL(deployment, project,
                                  utils.CREATE_CLUSTER_URL_ENDPOINT)
          },
          {
              "key":
                  "install-fci-config-url",
              "value":
                  utils.ConfigURL(deployment, project,
                                  utils.INSTALL_FCI_URL_ENDPOINT)
          },
          {
              "key": "volume-size-gb",
              "value": utils.ConvertVolumeSizeString(volume_size_gb)
          },
          {
              "key": "is-ad-node",
              "value": "false"
          },
          {
              "key": "is-master",
              "value": "true" if node_number == 0 else "false"
          },
          {
              "key": "ad-domain",
              "value": context.properties["domain"]
          },
          {
              "key": "domain-netbios",
              "value": context.properties["domain_netbios"]
          },
          {
              "key": "ad-node-ip",
              "value": utils.AdNodeIp(sql_cidr)
          },
          {
              "key": "service-account",
              "value": service_account
          },
          {
              "key": "service-password",
              "value": "$(ref.service-password.password)"
          },
          {
              "key": "safe-password",
              "value": "$(ref.safe-password.password)"
          },
          {
              "key": "my-node-name",
              "value": utils.NodeName(deployment, node_number)
          },
          {
              "key": "ad-node-name",
              "value": utils.AdNodeName(deployment)
          },
          {
              "key": "all-nodes",
              "value": utils.AllNodeNames(deployment, num_cluster_nodes)
          },
          {
              "key": "cluster-ip",
              "value": utils.ClusterIp(sql_cidr)
          },
          {
              "key": "application-ip",
              "value": utils.ApplicationIp(sql_cidr)
          },
          {
              "key": "zone",
              "value": zone
          },
          {
              "key": "instance-group",
              "value": utils.InstanceGroupName(deployment, zone)
          },
          {
              "key": "is-test",
              "value": is_test
          },
          {
              "key": "sql-fci-deployment-tag",
              "value": _SQL_FCI_TAG
          },
      ]
  }


def BuildAdNodeInstanceMetadata(context, zone):
  """Returns a list of key/value pairs for the AD node instance metadata.

  Args:
    context: The context of the deployment.
    zone: The zone where the VM will reside.

  Returns:
    A list of key value pairs specific to the AD node.
  """
  deployment = context.env["deployment"]
  project = context.env["project"]
  sql_cidr = context.properties.get("sql_cidr", utils.DEFAULT_DEPLOYMENT_CIDR)
  service_account = context.properties["service_account"]
  num_cluster_nodes = context.properties["num_cluster_nodes"]
  volume_size_gb = context.properties["volume_size_gb"]
  is_test = context.properties.get("dev_mode", "false")

  ad_node_name = utils.AdNodeName(deployment)

  return {
      "items": [
          {
              "key": "sysprep-specialize-script-ps1",
              "value": "Add-WindowsFeature \"RSAT-AD-Tools\""
          },
          {
              "key": "windows-startup-script-ps1",
              "value": context.imports["install.ps1"]
          },
          {
              "key": "wsfc-agent-port",
              "value": utils.HEALTH_CHECK_PORT
          },
          {
              "key":
                  "create-domain-config-url",
              "value":
                  utils.ConfigURL(deployment, project,
                                  utils.CREATE_DOMAIN_URL_ENDPOINT)
          },
          {
              "key":
                  "join-domain-config-url",
              "value":
                  utils.ConfigURL(deployment, project,
                                  utils.JOIN_DOMAIN_URL_ENDPOINT)
          },
          {
              "key":
                  "create-cluster-config-url",
              "value":
                  utils.ConfigURL(deployment, project,
                                  utils.CREATE_CLUSTER_URL_ENDPOINT)
          },
          {
              "key":
                  "install-fci-config-url",
              "value":
                  utils.ConfigURL(deployment, project,
                                  utils.INSTALL_FCI_URL_ENDPOINT)
          },
          {
              "key": "volume-size-gb",
              "value": utils.ConvertVolumeSizeString(volume_size_gb)
          },
          {
              "key": "is-ad-node",
              "value": "true"
          },
          {
              "key": "is-master",
              "value": "false"
          },
          {
              "key": "ad-domain",
              "value": context.properties["domain"]
          },
          {
              "key": "domain-netbios",
              "value": context.properties["domain_netbios"]
          },
          {
              "key": "ad-node-ip",
              "value": utils.AdNodeIp(sql_cidr)
          },
          {
              "key": "service-account",
              "value": service_account
          },
          {
              "key": "service-password",
              "value": "$(ref.service-password.password)"
          },
          {
              "key": "safe-password",
              "value": "$(ref.safe-password.password)"
          },
          {
              "key": "my-node-name",
              "value": ad_node_name
          },
          {
              "key": "ad-node-name",
              "value": ad_node_name
          },
          {
              "key": "all-nodes",
              "value": utils.AllNodeNames(deployment, num_cluster_nodes)
          },
          {
              "key": "cluster-ip",
              "value": utils.ClusterIp(sql_cidr)
          },
          {
              "key": "application-ip",
              "value": utils.ApplicationIp(sql_cidr)
          },
          {
              "key": "zone",
              "value": zone
          },
          {
              "key": "instance-group",
              "value": utils.InstanceGroupName(deployment, zone)
          },
          {
              "key": "is-test",
              "value": is_test
          },
          {
              "key": "sql-fci-deployment-tag",
              "value": _SQL_FCI_TAG
          },
      ]
  }


def ClusterVm(context, image, machine_type, zone, node_num):
  """Generates the config for a single cluster VM.

  Creates and returns a VM definition for a cluster node. The number of disks
  is determined by the user. The network configuration is determined through
  this nodes "node_num", which is a unique identifier for this node and so
  guarantees a unique IP address.

  Args:
    context: context of the deployment.
    image: full path name of the image to use to boot.
    machine_type: full path of the machine type.
    zone: the zone where the VM will reside.
    node_num: unique identifier of this VM.

  Raises:
    VmInputValidationError: if the node name is too long.

  Returns:
    VM definition of the cluster node.
  """
  project = context.env["project"]
  deployment = context.env["deployment"]
  sql_cidr = context.properties.get("sql_cidr", utils.DEFAULT_DEPLOYMENT_CIDR)
  net_name = utils.NetworkName(deployment)
  sub_name = utils.SubnetName(deployment)

  volume_size_gb = utils.ConvertVolumeSizeString(
      context.properties["volume_size_gb"])

  if volume_size_gb not in _VALID_VOLUME_SIZES:
    raise utils.VmInputValidationError(
        "volume size unsupported. Volume size must be one of {valid_sizes}")

  vm_name = utils.NodeName(deployment, node_num)

  if len(vm_name) > _MAX_NAME_LEN:
    raise utils.VmInputValidationError(
        "Deployment name is too long. Node names are based on deployment name"
        " and total length must be no longer than {} characters.".format(
            _MAX_NAME_LEN))

  resources = []
  disks = [BootDisk(vm_name, "cluster-boot-disk", project, zone, image)]

  # For each requested disk we need two disk definitions:
  # 1) A top level disk definition to go into the "resources". This is used
  #    to create the disk.
  # 2) A description of the disk to go in the instance definition. This is
  #    used to link the VM to a specific disk.
  for disk_num in xrange(_NUM_PD_SSD_DISKS):
    resources.append(
        Disk(project, zone, vm_name, _PD_SSD_DISK, disk_num,
             _VOLUME_TO_DISK_SIZE[volume_size_gb]))
    disks.append(VmDisk(vm_name, _PD_SSD_DISK, disk_num))

  nic = {
      default.ACCESS_CONFIGS: [{
          default.NAME: "external-nat",
          default.TYPE: default.ONE_NAT
      }],
      default.NETWORK: common.Ref(net_name),
      default.SUBNETWORK: common.Ref(sub_name),
      default.NETWORKIP: utils.NodeIp(sql_cidr, node_num)
  }

  instance = {
      default.ZONE:
          zone,
      # The service account is necessary for the VM to have access to google's
      # API. This will be used in scripts that set/get data related to
      # runtime watchers and configs.
      default.SERVICE_ACCOUNTS: [{
          "email":
              "default",
          "scopes": [
              "https://www.googleapis.com/auth/cloud-platform",
              "https://www.googleapis.com/auth/userinfo.email",
              "https://www.googleapis.com/auth/cloudruntimeconfig"
          ]
      }],
      default.MACHINETYPE:
          machine_type,
      default.DISKS:
          disks,
      default.NETWORK_INTERFACES: [nic],
      default.METADATA:
          BuildClusterInstanceMetadata(context, zone, node_num)
  }

  # We want the master node (node 0) to come up first so that it is
  # guaranteed to be the master. We do this by making all non-master nodes
  # depend on node 0
  deps = [] if node_num == 0 else [utils.NodeName(deployment, 0)]

  resources.append({
      default.NAME: vm_name,
      default.TYPE: default.INSTANCE,
      default.METADATA: {"dependsOn": deps},
      default.PROPERTIES: instance
  })

  return resources


def AdVm(context, machine_type, zone, image):
  """Creates a VM definition for the AD VM.

  This VM only has a single boot disk because it will not be a part of the
  cluster.

  Args:
    context: context of the deployment.
    machine_type: full path of the machine type.
    zone: The zone where the VM will reside.
    image: full path of the image to boot.

  Returns:
    definition of AD VM.
  """

  project = context.env["project"]
  deployment = context.env["deployment"]
  sql_cidr = context.properties.get("sql_cidr", utils.DEFAULT_DEPLOYMENT_CIDR)
  net_name = utils.NetworkName(deployment)
  sub_name = utils.SubnetName(deployment)

  ad_node_name = utils.AdNodeName(deployment)

  nic = {
      default.ACCESS_CONFIGS: [{
          default.NAME: "external-nat",
          default.TYPE: default.ONE_NAT,
      }],
      default.NETWORK: common.Ref(net_name),
      default.SUBNETWORK: common.Ref(sub_name),
      default.NETWORKIP: utils.AdNodeIp(sql_cidr)
  }

  instance = {
      default.ZONE:
          zone,
      default.MACHINETYPE:
          machine_type,
      default.SERVICE_ACCOUNTS: [{
          "email":
              "default",
          "scopes": [
              "https://www.googleapis.com/auth/cloud-platform",
              "https://www.googleapis.com/auth/userinfo.email",
              "https://www.googleapis.com/auth/cloudruntimeconfig"
          ]
      }],
      default.DISKS: [
          BootDisk(ad_node_name, "cntlr-boot-disk", project, zone, image)
      ],
      default.NETWORK_INTERFACES: [nic],
      default.METADATA:
          BuildAdNodeInstanceMetadata(context, zone)
  }

  return {
      default.NAME: ad_node_name,
      default.TYPE: default.INSTANCE,
      default.PROPERTIES: instance
  }


def ValidateVmContext(context):
  """Raises an exception if some input error is found.

  Args:
    context: Context of the deployment.

  Raises:
    VmInputValidationError: if there is a problem with the input
  """
  num_cluster_nodes = context.properties["num_cluster_nodes"]

  if not _MIN_CLUSTER_NODES <= num_cluster_nodes <= _MAX_CLUSTER_NODES:
    raise utils.VmInputValidationError(
        "Storage Space Direct requires at least "
        "{min_nodes} and at most {max_nodes} nodes.".format(
            min_nodes=_MIN_CLUSTER_NODES, max_nodes=_MAX_CLUSTER_NODES))

  num_disks_with_node_down = _NUM_PD_SSD_DISKS * (num_cluster_nodes - 1)
  if num_disks_with_node_down < _MIN_DISKS:
    raise utils.VmInputValidationError(
        ("S2D replication requires at least {num_disks} disks."
         " If one of your nodes goes down, you will only have"
         " {disks} in your deployment. Increase the number of "
         " disks in your VMs or the number of VMs in your "
         "deployment to have at least {num_disks} available "
         "with a node down.").format(
             num_disks=num_disks_with_node_down, disks=_MIN_DISKS))


def GenerateConfig(context):
  """Generates the config for the VMs in the deployment.

  Returns a dictionary with the configs constructed for the backend nodes
  and the ad node in the deployment. There is also an instance group that
  the backends are added to.

  Args:
    context: Context of the deployment.

  Returns:
    List of resources that the gcloud deployment-manager is to create.
  """

  ValidateVmContext(context)

  deployment = context.env["deployment"]
  num_cluster_nodes = context.properties["num_cluster_nodes"]
  region = context.properties["region"]
  net_name = utils.NetworkName(deployment)

  # list of top level resources to be returned to the gcloud deployment
  # orchestrator. Generate passwords for use in the windows apps install.
  resources = [{
      default.NAME: "service-password",
      default.TYPE: "password.py",
      default.PROPERTIES: {
          "length": 8,
          "includeSymbols": False,
      }
  }, {
      default.NAME: "safe-password",
      default.TYPE: "password.py",
      default.PROPERTIES: {
          "length": 14,
          "includeSymbols": True,
      }
  }]

  # list of instance names to be put in the instance group
  instances = []

  def _GetImagePath(family, image):
    return "{}projects/{}/global/images/{}".format(default.COMPUTE_URL_BASE,
                                                   family, image)

  def _GetMachinePath(zone):
    machine_type = utils.ConvertMachineTypeString(
        context.properties["machine_type"])
    return "{}projects/{}/zones/{}/machineTypes/{}".format(
        default.COMPUTE_URL_BASE, context.env["project"], zone, machine_type)

  for node_num in xrange(num_cluster_nodes):
    zone = utils.GetNodeZoneFromRegion(region, node_num)
    machine_type = _GetMachinePath(zone)
    vm = ClusterVm(context, _GetImagePath(
        _SQL_FCI_PUBLIC_FAMILY, _SQL_SVR_2016), machine_type, zone, node_num)

    resources.extend(vm)
    instances.append(common.Ref(utils.NodeName(deployment, node_num)))

  default_zone = utils.GetDefaultZoneFromRegion(region)
  resources.append(
      AdVm(context, _GetMachinePath(default_zone), default_zone,
           _GetImagePath(_SQL_FCI_PUBLIC_FAMILY, _WINDOWS_2016)))

  # The instance group will be used by the load balancer
  for instance_group_zone in utils.GetZoneSet(region, num_cluster_nodes):
    resources.append({
        default.NAME: utils.InstanceGroupName(deployment, instance_group_zone),
        default.TYPE: default.INSTANCE_GROUP,
        default.PROPERTIES: {
            default.ZONE: instance_group_zone,
            default.NETWORK: common.Ref(net_name),
        }
    })

  return {
      "resources": resources,
  }
