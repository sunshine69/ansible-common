#!/usr/bin/env python

DOCUMENTATION = '''
module: aws_elasticsearch_facts
(stevek TODO) Add usage examples here
'''

try:
    import json
    import botocore
    import boto3

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

def empty_result(module):

    return {
        "DomainStatus": {
            "DomainName": module.params.get("domain_name"),
            "ElasticsearchClusterConfig": {
                'DedicatedMasterCount': 0,
                'InstanceCount': 0
            }
        }
    }

def list_es_domains(client, module):
    params = {}
    params['DomainName'] = module.params.get("domain_name")

    try:
        result = client.describe_elasticsearch_domain(**params)
        result.pop("ResponseMetadata")
        return result
    except botocore.exceptions.ClientError as e:
        return empty_result(module)

def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        domain_name=dict()
        ),
    )
    module = AnsibleModule(argument_spec=argument_spec)

    if not HAS_BOTO3:
        module.fail_json(msg='json and boto3 is required.')
    try:
        region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
        client = boto3_conn(module, conn_type='client', resource='es', region=region, **aws_connect_kwargs)
    except botocore.exceptions.NoCredentialsError, e:
        module.fail_json(msg="Can't authorize connection - "+str(e))
    results = list_es_domains(client, module)
    module.exit_json(result=results)

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()
