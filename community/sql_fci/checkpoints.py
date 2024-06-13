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
"""Configs and Waiters used for checkpointing parts of the deployment.

This file just provides a series of "checkpoints" for the deployment,
implemented by using a config's URL to block on, and a waiter to block the
creation of the next config.

Without the context of google's deployment manager system, this file will
probably not make any sense. For the necessary background please see:

https://cloud.google.com/deployment-manager/docs/

for the necessary background.

NOTE: Imports in this module must be relative, as this module will not have
access to google3 where it will be run.
"""

import default
import utils


_CONFIG_TYPE = "runtimeconfig.v1beta1.config"
_WAITER_TYPE = "runtimeconfig.v1beta1.waiter"


def CreateConfigDefinition(name, deps=None):
  """Returns a definition of a runtime config.

  Args:
    name: the name of the config as a string
    deps: a list of strings, each of which is a dependency to wait for.

  Returns:
    A definition of a runtime config as a dict
  """
  return {
      default.NAME: name,
      default.METADATA: {
          "dependsOn": deps or []
      },
      default.TYPE: _CONFIG_TYPE,
      default.PROPERTIES: {
          "config": name,
          "description": "marker for the beginning of the {} phase".format(
              name)
      }
  }


def CreateWaiterDefinition(name, parent, success_num, timeout=1600, deps=None):
  """Returns a definition of a runtime waiter.

  Args:
    name: the name of the waiter as a string
    parent: the name of the config, as a string, that this waiter will watch on.
    success_num: the required number of successes before this
      waiter completes.
    timeout: number of seconds before this waiter will abort.
    deps: a list of strings, each of which is a dependency to wait for.

  Returns:
    A definition of a runtime waiter as a dict.
  """
  return {
      default.NAME: name,
      default.TYPE: _WAITER_TYPE,
      default.METADATA: {
          "dependsOn": deps or []
      },
      default.PROPERTIES: {
          "parent": "$(ref.{}.name)".format(parent),
          "waiter": name,
          "timeout": "{}s".format(timeout),
          "success": {
              "cardinality": {
                  "number": success_num,
                  "path": "success"
              }
          },
          "failure": {
              "cardinality": {
                  "number": 1,
                  "path": "failure"
              }
          }
      },
  }


def GenerateConfig(context):
  """Returns a list of configs and waiters for this deployment.

  The configs and waiters define a series of phases that the deployment will
  go through. This is a way to "pause" the deployment while some process on
  the VMs happens, checks for success, then goes to the next phase.

  The configs here define the phases, and the waiters "wait" for the phases
  to be complete.

  The phases are:
    CREATE_DOMAIN: the Windows Active Directory node installs and sets up the
                   Active Directory.
    JOIN_DOMAIN: all nodes join the domain set up by the Active Directory node.
    CREATE_CLUSTER: creates the failover cluster, enables S2D
    INSTALL_FCI: Installs SQL FCI on all non-master nodes.

  Args:
    context: the context of the deployment. This is a class that will have
             "properties" and "env" dicts containing parameters for the
             deployment.

  Returns:
    A list of dicts, which are the definitions of configs and waiters.
  """

  num_cluster_nodes = context.properties["num_cluster_nodes"]
  deployment = context.env["deployment"]

  create_domain_config_name = utils.ConfigName(
      deployment, utils.CREATE_DOMAIN_URL_ENDPOINT)
  create_domain_waiter_name = utils.WaiterName(
      deployment, utils.CREATE_DOMAIN_URL_ENDPOINT)

  join_domain_config_name = utils.ConfigName(
      deployment, utils.JOIN_DOMAIN_URL_ENDPOINT)
  join_domain_waiter_name = utils.WaiterName(
      deployment, utils.JOIN_DOMAIN_URL_ENDPOINT)

  # This is the list of resources that will be returned to the deployment
  # manager so that the deployment manager can create them. Every Item in this
  # list will have a dependency on the item before it so that they are created
  # in order.

  cluster_config_name = utils.ConfigName(
      deployment, utils.CREATE_CLUSTER_URL_ENDPOINT)
  cluster_waiter_name = utils.WaiterName(
      deployment, utils.CREATE_CLUSTER_URL_ENDPOINT)

  fci_config_name = utils.ConfigName(
      deployment, utils.INSTALL_FCI_URL_ENDPOINT)
  fci_waiter_name = utils.WaiterName(
      deployment, utils.INSTALL_FCI_URL_ENDPOINT)

  resources = [
      CreateConfigDefinition(create_domain_config_name),
      CreateWaiterDefinition(
          create_domain_waiter_name,
          create_domain_config_name,
          1,
          deps=[create_domain_config_name]),
      CreateConfigDefinition(
          join_domain_config_name,
          deps=[create_domain_waiter_name]),
      CreateWaiterDefinition(
          join_domain_waiter_name,
          join_domain_config_name,
          num_cluster_nodes,
          deps=[join_domain_config_name]),
      CreateConfigDefinition(
          cluster_config_name,
          deps=[join_domain_waiter_name]),
      CreateWaiterDefinition(
          cluster_waiter_name,
          cluster_config_name,
          1,
          deps=[cluster_config_name]),
      CreateConfigDefinition(
          fci_config_name,
          deps=[cluster_waiter_name]),
      CreateWaiterDefinition(
          fci_waiter_name,
          fci_config_name,
          # -1 to account for the fact that the master already set up
          # FCI by this point.
          (num_cluster_nodes - 1),
          deps=[fci_config_name])
  ]

  return {
      "resources": resources,
  }
