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
"""Generates a config defining the network in the deployment.

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


def FirewallRule(name, net_name, protocol, deployment, sources, ports=None):
  """Creates a Firewall Rule definition.

  Returns a firewall definition based on arguments that is compatible with
  the gcloud.

  Args:
    name: string name of the firewall rule
    net_name: string name of the network that this rule will apply to.
    protocol: The network protocol, e.g. 'ICMP', 'TCP', 'UDP'
    deployment: name of this deployment.
    sources: list of strings cidrs of traffic to be allowed.
    ports: the TCP or UDP ports that this firewall rule will apply to.

  Returns:
    Firewall Rule definition compatible with gcloud deployment launcher.
  """
  allowed = {
      default.IP_PROTO: protocol
  }

  if ports:
    allowed.update({default.PORTS: [ports]})

  properties = {
      default.NETWORK: common.Ref(net_name).format(net_name),
      default.ALLOWED: [allowed],
      default.SRC_RANGES: sources
  }

  firewall_rule_name = "{deployment}-{name}".format(
      deployment=deployment,
      name=name)

  return {
      default.NAME: firewall_rule_name,
      default.TYPE: default.FIREWALL,
      default.PROPERTIES: properties
  }


def GenerateConfig(context):
  """Generates the network configuration for the gcloud deployment.

  Args:
    context: context of the deployment.

  Returns:
    List of resources that the deployment manager will create.
  """

  region = context.properties["region"]
  sql_cidr = context.properties.get("sql_cidr", utils.DEFAULT_DEPLOYMENT_CIDR)
  deployment = context.env["deployment"]
  net_name = utils.NetworkName(deployment)
  sub_name = utils.SubnetName(deployment)
  is_test = context.properties.get("dev_mode", "false")

  resources = [
      {
          default.NAME: net_name,
          default.TYPE: default.NETWORK_TYPE,
          default.PROPERTIES: {
              default.AUTO_CREATE_SUBNETWORKS: False,
          }
      },
      {
          default.NAME: sub_name,
          default.TYPE: default.SUBNETWORK_TYPE,
          default.PROPERTIES: {
              default.NETWORK: common.Ref(net_name),
              default.REGION: region,
              default.IP_CIDR_RANGE: sql_cidr
          }
      },
      # Allow ICMP for debugging
      FirewallRule(
          "allow-all-icmp", net_name, "ICMP", deployment, sources=[sql_cidr]),

      # Allow RDP, SQL, and Load Balancer Health Check from anywhere
      FirewallRule(
          "allow-rdp-port",
          net_name,
          "TCP",
          deployment,
          sources=["0.0.0.0/0"],
          ports="3389"),
      FirewallRule(
          "allow-health-check-port",
          net_name,
          "TCP",
          deployment,
          # The Google ILB health check service IP ranges.
          sources=["130.211.0.0/22", "35.191.0.0/16"],
          ports=utils.HEALTH_CHECK_PORT),

      # Allow ALL TCP and UDP traffic from within the same network. We should
      # only have cluster and AD nodes on this network so the traffic is
      # trusted.
      FirewallRule(
          "allow-all-udp",
          net_name,
          "UDP",
          deployment,
          sources=[sql_cidr],
          ports="0-65535"),
      FirewallRule(
          "allow-all-tcp",
          net_name,
          "TCP",
          deployment,
          sources=[sql_cidr],
          ports="0-65535"),
  ]

  if is_test:
    resources.append(
        FirewallRule(
            "allow-sql-port",
            net_name,
            "TCP",
            deployment,
            sources=["0.0.0.0/0"],
            ports=utils.APPLICATION_PORT))

  return {"resources": resources}
