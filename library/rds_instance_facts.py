#!/usr/bin/python
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

ANSIBLE_METADATA = {'status': ['preview'],
                    'supported_by': 'community',
                    'version': '1.0'}

DOCUMENTATION = '''
---
module: rds_instance_facts
version_added: "2.3"
short_description: obtain facts about one or more RDS instances
description:
  - obtain facts about one or more RDS instances
options:
  name:
    description:
      - Name of an RDS instance.
    required: false
    aliases: name
  filters:
    description:
      - A filter that specifies one or more DB instances to describe.
requirements:
    - "python >= 2.6"
    - "boto3"
author:
    - "Bruce Pennypacker (@bpennypacker)"
    - "Will Thames (@willthames)"
extends_documentation_fragment:
    - aws
    - ec2
'''

EXAMPLES = '''
# Get facts about an instance
- rds_instance_facts:
    name: new-database
  register: new_database_facts

# Get all RDS instances
- rds_instance_facts:
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.ec2 import ec2_argument_spec, get_aws_connection_info, boto3_conn, HAS_BOTO3
from ansible.module_utils.ec2 import ansible_dict_to_boto3_filter_list, camel_dict_to_snake_dict

import traceback

try:
    import botocore
except:
    pass  # caught by imported HAS_BOTO3


def get_db_instance(conn, instancename):
    try:
        response = conn.describe_db_instances(DBInstanceIdentifier=instancename)
        instance = RDSDBInstance(response['DBInstances'][0])
        return instance
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'DBInstanceNotFound':
            return None
        else:
            raise


def get_db_snapshot(conn, snapshotid):
    try:
        response = conn.describe_db_snapshots(DBSnapshotIdentifier=snapshotid)
        snapshot = RDSSnapshot(response['DBSnapshots'][0])
        return snapshot
    except botocore.exceptions.ClientError:
        if e.response['Error']['Code'] == 'DBSnapshotNotFound':
            return None
        else:
            raise


class RDSDBInstance(object):
    def __init__(self, dbinstance):
        self.instance = dbinstance
        if 'DBInstanceIdentifier' not in dbinstance:
            self.name = None
        else:
            self.name = self.instance.get('DBInstanceIdentifier')
        self.status = self.instance.get('DBInstanceStatus')
        self.data = self.get_data()

    def get_data(self):
        d = {
            'id': self.name,
            'create_time': self.instance.get('InstanceCreateTime', ''),
            'db_engine': self.instance['Engine'],
            'db_name': self.instance.get('DBName'),
            'status': self.status,
            'availability_zone': self.instance.get('AvailabilityZone'),
            'backup_retention': self.instance['BackupRetentionPeriod'],
            'maintenance_window': self.instance['PreferredMaintenanceWindow'],
            'multi_zone': self.instance['MultiAZ'],
            'instance_type': self.instance['DBInstanceClass'],
            'username': self.instance['MasterUsername'],
            'replication_source': self.instance.get('ReadReplicaSourceDBInstanceIdentifier'),
            'size': self.instance.get('AllocatedStorage'),
            'storage_type': self.instance.get('StorageType')
        }
        if self.instance.get('Iops'):
            d['iops'] = self.instance['Iops'],
        if self.instance["VpcSecurityGroups"] is not None:
            d['vpc_security_groups'] = ','.join(x['VpcSecurityGroupId'] for x in self.instance['VpcSecurityGroups'])
        if self.instance.get("Endpoint"):
            d['endpoint'] = self.instance["Endpoint"].get('Address', None)
            d['port'] = self.instance["Endpoint"].get('Port', None)
        else:
            d['endpoint'] = None
            d['port'] = None
        if self.instance.get("Tags"):
            d['tags'] = boto3_tag_list_to_ansible_dict(self.instance.get("Tags"))

        return d

    def diff(self, params):
        compare_keys = ['backup_retention', 'instance_type', 'iops',
                        'maintenance_window', 'multi_zone',
                        'replication_source',
                        'size','storage_type', 'tags', 'zone']
        before = dict()
        after = dict()
        for k in compare_keys:
            if self.instance.get(k) != params.get(k):
                before[k] = self.instance.get(k)
                after[k] = params.get(k)
        port = self.data.get('port')
        if port != params.get('port'):
            before['port'] = port
            after['port'] = params.get('port')
        result = dict()
        if before:
            result = dict(before_header=self.name, before=before, after=after)
            result['after_header'] = params.get('new_instance_name', params['instance_name'])
        return result

    def __eq__(self, other):
        return self.diff(other.instance)

    def __ne__(self, other):
        return not self == other


class RDSSnapshot(object):
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.name = self.snapshot.get('DBSnapshotIdentifier')
        self.status = self.snapshot.get('Status')
        self.data = self.get_data()

    def get_data(self):
        d = {
            'id': self.name,
            'create_time': self.snapshot.get('SnapshotCreateTime', ''),
            'status': self.status,
            'availability_zone': self.snapshot['AvailabilityZone'],
            'instance_id': self.snapshot['DBInstanceIdentifier'],
            'instance_created': self.snapshot['InstanceCreateTime'],
            'snapshot_type': self.snapshot['SnapshotType'],
        }
        if self.snapshot.get('Iops'):
            d['iops'] = self.snapshot['Iops'],
        return d


def instance_facts(module, conn):
    instance_name = module.params.get('name')
    filters = module.params.get('filters')

    params = dict()
    if instance_name:
        params['DBInstanceIdentifier'] = instance_name
    if filters:
        params['Filters'] = ansible_dict_to_boto3_filter_list(filters)

    marker = ''
    results = list()
    while True:
        try:
            response = conn.describe_db_instances(Marker=marker, **params)
            results.extend(response['DBInstances'])
            marker = response.get('Marker')
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'DBInstanceNotFound':
                break
            module.fail_json(msg=str(e), exception=traceback.format_exc(),
                             **camel_dict_to_snake_dict(e.response))
        if not marker:
            break

    module.exit_json(changed=False, instances=[RDSDBInstance(instance).data for instance in results])


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(
        dict(
            name = dict(aliases=['instance_name']),
            filters = dict(type='list', default=[])
        )
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_BOTO3:
        module.fail_json(msg="botocore and boto3 are required for rds_facts module")

    region, ec2_url, aws_connect_params = get_aws_connection_info(module, boto3=True)
    if not region:
        module.fail_json(msg="Region not specified. Unable to determine region from configuration.")

    # connect to the rds endpoint
    conn = boto3_conn(module, 'client', 'rds', region, **aws_connect_params)

    instance_facts(module, conn)


main()
