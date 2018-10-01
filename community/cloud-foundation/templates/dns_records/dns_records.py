# Copyright 2018 Google Inc. All rights reserved.
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
"""This template creates DNS records for a managed zone."""

import string
import random


def generate_config(context):
    """ Entry point for the deployment resources.
    For each ResourceRecordSet, create a resource with an action to
    create, and another resource with an action to delete.
    To ensure that the action name is unique, 
    create a random string and append it to the field value.
    """

    resources = []
    random_string_len = 10

    zonename = context.properties['zoneName']
    for resource_recordset in context.properties['resourceRecordSets']:
        deployment_name = generate_unique_string(random_string_len)
        recordset_create = {
            'name': deployment_name + '-create',
            'action': 'gcp-types/dns-v1:dns.changes.create',
            'metadata': {
                'runtimePolicy': [
                    'CREATE',
                ],
            },
            'properties':
                {
                    'managedZone': zonename,
                    'additions': [resource_recordset]
                },
        }
        recordset_delete = {
            'name': deployment_name + '-delete',
            'action': 'gcp-types/dns-v1:dns.changes.create',
            'metadata': {
                'runtimePolicy': [
                    'DELETE',
                ],
            },
            'properties':
                {
                    'managedZone': zonename,
                    'deletions': [resource_recordset]
                },
        }

        resources.append(recordset_create)
        resources.append(recordset_delete)

    return {'resources': resources}


def generate_unique_string(num_chars):
    """ Generate a random alphanumeric string.
    The length of the returned string is num_chars
    """

    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for x in range(num_chars))
