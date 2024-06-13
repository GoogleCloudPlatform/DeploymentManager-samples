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


def GenerateConfig(context):
  """Returns a list of resources that represent the entire deployment.

  Args:
    context: context of the deployment.

  Returns:
    List of resources that the deployment will create.
  """
  resources = [{
      'name': 'sql_network',
      'type': 'sql_network.py',
      'properties': context.properties
  }, {
      'name': 'vms',
      'type': 'vms.py',
      'properties': context.properties
  }, {
      'name': 'internal_lb',
      'type': 'internal_lb.py',
      'properties': context.properties
  }, {
      'name': 'checkpoints',
      'type': 'checkpoints.py',
      'properties': context.properties
  }]

  return {'resources': resources}
