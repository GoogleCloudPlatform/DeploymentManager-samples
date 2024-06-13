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
"""Top level google cloud deployment definition.

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


BACKEND_SERVICE_NAME = 'cluster-backend-service'
FORWARD_RULE_NAME = 'lb-forward-rule'


def _BackendServiceName(deployment):
  return '{deployment}-{name}'.format(
      deployment=deployment, name=BACKEND_SERVICE_NAME)


def _ForwardRuleName(deployment):
  return '{deployment}-{name}'.format(
      deployment=deployment, name=FORWARD_RULE_NAME)


def HealthCheck(deployment, health_check_port, application_ip):
  """Returns a definition of a health check.

  Args:
    deployment: the name of this deployment.
    health_check_port: the port to perform the health check on.
    application_ip: the ip to perform the health check on.

  Returns:
    A definition of a health check.
  """
  return {
      default.NAME: utils.HealthCheckName(deployment),
      default.TYPE: 'compute.v1.healthCheck',
      default.PROPERTIES: {
          default.TYPE: 'TCP',
          default.TCP_HEALTH_CHECK: {
              default.PORT: health_check_port,
              'request': application_ip,
              'response': 1
          }
      }
  }


def BackendService(region, deployment, net_name, num_cluster_nodes):
  """Returns a definition of a backend service.

  Args:
    region: The region that this backend service will be deployed to.
    deployment: The name of this deployment.
    net_name: The name of the network that this backend service will operate on.
    num_cluster_nodes: number of cluster nodes in the deployment

  Returns:
    A definition of a backend service.
  """
  backends = []
  for zone in utils.GetZoneSet(region, num_cluster_nodes):
    backends.append({
        'group': common.Ref(utils.InstanceGroupName(deployment, zone))
    })
  return {
      default.NAME: _BackendServiceName(deployment),
      default.TYPE: default.REGION_BACKEND_SERVICE,
      default.PROPERTIES: {
          default.REGION:
              region,
          default.NETWORK:
              common.Ref(net_name),
          default.BACKENDS:
              backends,
          default.HEALTH_CHECKS: [
              common.Ref(utils.HealthCheckName(deployment))
          ],
          default.PROTOCOL:
              'TCP',
          default.LB_SCHEME:
              'INTERNAL'
      }
  }


def ForwardingRule(deployment, region, port, cidr, net_name, sub_name):
  """Returns a definition of a forwarding rule.

  Args:
    deployment: The name of this deployment.
    region: The region that this backend service will be deployed to.
    port: The port of the traffic to forward.
    cidr: string representing the cidr in a.b.c.d/x form.
    net_name: The name of the network that this backend service will operate on.
    sub_name: The name of the subnet that this backend service will operate on.

  Returns:
    The definition of the forwarding rule.
  """
  return {
      default.NAME: _ForwardRuleName(deployment),
      default.TYPE: default.FORWARDING_RULE,
      default.PROPERTIES: {
          default.PORTS: [port],
          default.IP_ADDRESS: utils.ApplicationIp(cidr),
          default.NETWORK: common.Ref(net_name),
          default.SUBNETWORK: common.Ref(sub_name),
          default.REGION: region,
          'backendService': common.Ref(_BackendServiceName(deployment)),
          default.LB_SCHEME: 'INTERNAL'
      }
  }


def GenerateConfig(context):
  """Generates resources based on properties.

  Args:
    context: the context of this deployment.

  Returns:
    list of resources required to set up the load balancer service.
  """
  deployment = context.env['deployment']
  region = context.properties['region']
  net_name = utils.NetworkName(deployment)
  sub_name = utils.SubnetName(deployment)
  sql_cidr = context.properties.get('sql_cidr', utils.DEFAULT_DEPLOYMENT_CIDR)
  application_ip = utils.ApplicationIp(sql_cidr)
  num_cluster_nodes = context.properties['num_cluster_nodes']
  return {
      'resources': [
          HealthCheck(deployment, utils.HEALTH_CHECK_PORT, application_ip),
          BackendService(region, deployment, net_name, num_cluster_nodes),
          ForwardingRule(deployment, region, utils.APPLICATION_PORT, sql_cidr,
                         net_name, sub_name)
      ]
  }
