# (c) 2016, Mike Mochan <@mmochan>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
DOCUMENTATION = '''
module: cloudwatch_log
short_description: create, modify and delete AutoScaling Scheduled Actions.
description:
  - Read the AWS documentation for CloudWatch Logs
    U(http://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/WhatIsCloudWatchLogs.html
version_added: "2.2"
options:
  logGroupNamePrefix:
    description:
      - The name of the LogGroup.
    required: true
  limit:
    description:
      - The max number of items to return.
    required: false
    default: 99
  state:
    description:
      - present, absent
    required: false
    default: present
    choices: ['present', 'absent']
author: Mike Mochan(@mmochan)
extends_documentation_fragment: aws
'''

EXAMPLES = '''
# Create a CloudWatch LogGroup.


'''
RETURN = '''
task:
  description: The result of the present, and absent actions.
  returned: success
  type: dictionary
'''

try:
    import json
    import botocore
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

from dateutil.tz import tzutc
import datetime


def create_log_group(client, name):
    try:
        return client.create_log_group(logGroupName=name)
    except botocore.exceptions.ClientError as e:
        module.fail_json(msg=str(e))


def delete_log_group(client, module, name):
    try:
        return client.delete_log_group(logGroupName=name)
    except botocore.exceptions.ClientError as e:
        module.fail_json(msg=str(e))


def describe_log_groups(client, module, filter_prefix):
    try:
        return client.describe_log_groups(logGroupNamePrefix=filter_prefix,
                                          limit=50)
    except botocore.exceptions.ClientError as e:
        module.fail_json(msg=str(e))


def list_groups(client, module):
    changed = False
    result = None
    filter_prefix = module.params.get('filter_prefix')
    result = describe_log_groups(client, module, filter_prefix)
    return changed, result


def setup(client, module):
    changed = False
    result = None
    name = module.params.get('log_group_name')
    filter_prefix = module.params.get('filter_prefix')
    log_groups = describe_log_groups(client, module, filter_prefix)
    if not log_groups['logGroups']:
        changed = True
        result = create_log_group(client, name)
    else:
        result = log_groups
    return changed, result


def teardown(client, module):
    changed = False
    result = None
    name = module.params.get('log_group_name')
    filter_prefix = module.params.get('filter_prefix')
    log_groups = describe_log_groups(client, module, filter_prefix)
    if log_groups['logGroups']:
        result = delete_log_group(client, module, name)
        changed = True
    return changed, result


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        log_group_name=dict(default=None, required=False),
        filter_prefix=dict(default=None, required=False),
        state=dict(default='present', choices=['present', 'absent', 'list'])
        )
    )
    module = AnsibleModule(argument_spec=argument_spec)
    state = module.params.get('state').lower()

    if not HAS_BOTO3:
        module.fail_json(msg='json and boto3 are required.')

    try:
        region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
        client = boto3_conn(module, conn_type='client', resource='logs', region=region, endpoint=ec2_url, **aws_connect_kwargs)       
    except botocore.exceptions.NoCredentialsError, e:
        module.fail_json(msg="Can't authorize connection - " + str(e))

    invocations = {
        "present": setup,
        "absent": teardown,
        "list": list_groups
    }

    (changed, results) = invocations[state](client, module)
    module.exit_json(changed=changed, results=results)


# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()
