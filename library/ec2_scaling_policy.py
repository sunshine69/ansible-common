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

ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['stableinterface'],
                    'supported_by': 'curated'}


DOCUMENTATION = """
module: ec2_scaling_policy
short_description: Create or delete AWS scaling policies for Autoscaling groups
description:
  - Can create or delete scaling policies for autoscaling groups
  - Referenced autoscaling groups must already exist
version_added: "1.6"
author:
  - Zacharie Eakin (@zeekin)
  - Will Thames (@willthames)
options:
  state:
    description:
      - register or deregister the policy
    required: true
    choices: ['present', 'absent']
  name:
    description:
      - Unique name for the scaling policy
    required: true
  asg_name:
    description:
      - Name of the associated autoscaling group. Required if I(state) is C(present).
  adjustment_type:
    description:
      - The type of change in capacity of the autoscaling group. Required if I(state) is C(present).
    choices:
      - ChangeInCapacity
      - ExactCapacity
      - PercentChangeInCapacity
  scaling_adjustment:
    description:
      - The amount by which the autoscaling group is adjusted by the policy.
        A negative number scales the autoscaling group in. Units are numbers
        of instances for C(ExactCapacity) or C(ChangeInCapacity) or percent
        of existing instances for C(PercentChangeInCapacity).
        Required when I(policy_type) is C(SimpleScaling).
  min_adjustment_step:
    description:
      - Minimum amount of adjustment when policy is triggered. Used
        only when I(adjustment_type) is C(PercentChangeInCapacity)
  cooldown:
    description:
      - The minimum period of time between which autoscaling actions can take place.
        Used only when I(policy_type) is C(SimpleScaling).
  policy_type:
    description:
      - Auto scaling adjustment policy
    choices:
      - StepScaling
      - SimpleScaling
    version_added: 2.4
    default: SimpleScaling
  metric_aggregation:
    description:
      - The aggregation type for the CloudWatch metrics.
      - For use when I(policy_type) is not C(SimpleScaling)
    default: Average
    choices:
      - Minimum
      - Maxium
      - Average
    version_added: 2.4
  step_adjustments:
    description:
      - list of dicts containing I(lower_bound), I(upper_bound) and I(scaling_adjustment)
      - One item can not have a lower bound, and one item can not have an upper bound.
      - Intervals must not overlap
      - The bounds are the amount over the alarm threshold at which the adjustment will trigger.
        This means that for an alarm threshold of 50, triggering at 75 requires a lower bound of 25.
        See U(http://docs.aws.amazon.com/AutoScaling/latest/APIReference/API_StepAdjustment.html).
    version_added: 2.4
  estimated_instance_warmup:
    description:
      - The estimated time, in seconds, until a newly launched instance can contribute to the CloudWatch metrics.
    version_added: 2.4
extends_documentation_fragment:
    - aws
    - ec2
"""

EXAMPLES = '''
- name: Simple Scale Down policy
  ec2_scaling_policy:
    state: present
    region: US-XXX
    name: "scaledown-policy"
    adjustment_type: "ChangeInCapacity"
    asg_name: "application-asg"
    scaling_adjustment: -1
    min_adjustment_step: 1
    cooldown: 300

# For an alarm with a breach threshold of 20, the 
# following creates a stepped policy:
# From 20-40 (0-20 above threshold), increase by 50% of existing capacity
# From 41-infinity, increase by 100% of existing capacity
- ec2_scaling_policy:
    state: present
    region: US-XXX
    name: "step-scale-up-policy"
    policy_type: StepScaling
    metric_aggregation: Maximum
    step_adjustments:
      - upper_bound: 20
        scaling_adjustment: 50
      - lower_bound: 21
        scaling_adjustment: 100
    adjustment_type: "PercentChangeInCapacity"
    asg_name: "application-asg"
'''

import traceback

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.ec2 import ec2_argument_spec, boto3_conn, get_aws_connection_info
from ansible.module_utils.ec2 import HAS_BOTO3, camel_dict_to_snake_dict

try:
    import botocore
except ImportError:
    pass  # caught by imported HAS_BOTO3


def create_scaling_policy(connection, module):
    changed = False
    asg_name = module.params['asg_name']
    policy_type = module.params['policy_type']
    policy_name = module.params['name']

    params = dict(PolicyName=policy_name,
                  PolicyType=policy_type,
                  AutoScalingGroupName=asg_name,
                  AdjustmentType=module.params['adjustment_type'])

    # min_adjustment_step attribute is only relevant if the adjustment_type
    # is set to percentage change in capacity, so it is a special case
    if module.params['adjustment_type'] == 'PercentChangeInCapacity':
        if module.params['min_adjustment_step']:
            params['MinAdjustmentMagnitude'] = module.params['min_adjustment_step']

    if policy_type == 'SimpleScaling':
        # can't use required_if because it doesn't allow multiple criteria -
        # it's only required if policy is SimpleScaling and state is present
        if not module.params['scaling_adjustment']:
            module.fail_json(msg='scaling_adjustment is required when policy_type is SimpleScaling '
                             'and state is present')
        params['ScalingAdjustment'] = module.params['scaling_adjustment']
        if module.params['cooldown']:
            params['Cooldown'] = module.params['cooldown']

    if policy_type == 'StepScaling':
        if not module.params['step_adjustments']:
            module.fail_json(msg='step_adjustments is required when policy_type is StepScaling '
                             'and state is present')
        params['StepAdjustments'] = []
        for step_adjustment in module.params['step_adjustments']:
            step_adjust_params = dict(ScalingAdjustment=step_adjustment['scaling_adjustment'])
            # Although empty bounds are allowed, not setting the 0 end of the bound seems
            # to cause problems in the UI. We'll leave the +/- infinity end unset if not set
            if not step_adjustment.get('lower_bound') and step_adjustment.get('upper_bound') > 0:
                step_adjustment['lower_bound'] = 0
            if step_adjustment.get('lower_bound'):
                step_adjust_params['MetricIntervalLowerBound'] = step_adjustment['lower_bound']
            if not step_adjustment.get('upper_bound') and step_adjustment.get('lower_bound') < 0:
                step_adjustment['upper_bound'] = 0
            if step_adjustment.get('upper_bound'):
                step_adjust_params['MetricIntervalUpperBound'] = step_adjustment['upper_bound']
            params['StepAdjustments'].append(step_adjust_params)
        if module.params['metric_aggregation']:
            params['MetricAggregationType'] = module.params['metric_aggregation']
        if module.params['estimated_instance_warmup']:
            params['EstimatedInstanceWarmup'] = module.params['estimated_instance_warmup']

    try:
        policies = connection.describe_policies(AutoScalingGroupName=asg_name,
                                                PolicyNames=[policy_name])['ScalingPolicies']
    except botocore.exceptions.ClientError as e:
        module.fail_json(msg="Failed to obtain autoscaling policy %s" % policy_name,
                         exception=traceback.format_exc(),
                         **camel_dict_to_snake_dict(e.response))

    before = after = {}
    if not policies:
        changed = True
    else:
        policy = policies[0]
        for key in params:
            if params[key] != policy.get(key):
                changed = True
                before[key] = params[key]
                after[key] = policy.get(key)

    if changed:
        try:
            connection.put_scaling_policy(**params)
        except botocore.exceptions.ClientError as e:
            module.fail_json(msg="Failed to create autoscaling policy",
                             exception=traceback.format_exc(),
                             **camel_dict_to_snake_dict(e.response))
        try:
            policies = connection.describe_policies(AutoScalingGroupName=asg_name,
                                                    PolicyNames=[policy_name])['ScalingPolicies']
        except botocore.exceptions.ClientError as e:
            module.fail_json(msg="Failed to obtain autoscaling policy %s" % policy_name,
                             exception=traceback.format_exc(),
                             **camel_dict_to_snake_dict(e.response))

    policy = camel_dict_to_snake_dict(policies[0])
    # Backward compatible return values
    policy['arn'] = policy['policy_arn']
    policy['as_name'] = policy['auto_scaling_group_name']
    policy['name'] = policy['policy_name']

    if before and after:
        module.exit_json(changed=changed, diff=dict(before=before, after=after), **policy)
    else:
        module.exit_json(changed=changed, **policy)


def delete_scaling_policy(connection, module):
    sp_name = module.params.get('name')

    try:
        policy = connection.describe_policies(PolicyNames=[sp_name])
    except botocore.exceptions.ClientError as e:
        module.fail_json(msg="Failed to obtain autoscaling policy %s" % policy_name,
                         exception=traceback.format_exc(),
                         **camel_dict_to_snake_dict(e.response))

    if policy['ScalingPolicies']:
        try:
            connection.delete_policy(AutoScalingGroupName=policy['ScalingPolicies'][0]['AutoScalingGroupName'],
                                     PolicyName=sp_name)
            module.exit_json(changed=True)
        except botocore.exceptions.ClientError as e:
            module.fail_json(msg="Failed to delete autoscaling policy",
                             exception=traceback.format_exc(), **camel_dict_to_snake_dict(e.response))
    else:
        module.exit_json(changed=False)


def main():
    step_adjustment_spec = dict(
        lower_bound=dict(type='int'),
        upper_bound=dict(type='int'),
        scaling_adjustment=dict(type='int', required=True))

    argument_spec = ec2_argument_spec()
    argument_spec.update(
        dict(
            name=dict(required=True),
            adjustment_type=dict(choices=['ChangeInCapacity', 'ExactCapacity', 'PercentChangeInCapacity']),
            asg_name=dict(),
            scaling_adjustment=dict(type='int'),
            min_adjustment_step=dict(type='int'),
            cooldown=dict(type='int'),
            state=dict(default='present', choices=['present', 'absent']),
            metric_aggregation=dict(default='Average', choices=['Average', 'Maximum', 'Minimum']),
            policy_type=dict(default='SimpleScaling', choices=['SimpleScaling', 'StepScaling']),
            step_adjustments=dict(type='list', options=step_adjustment_spec),
            estimated_instance_warmup=dict(type='int')
        )
    )

    module = AnsibleModule(argument_spec=argument_spec,
                           required_if=[['state', 'present', ['asg_name', 'adjustment_type']]])

    if not HAS_BOTO3:
        module.fail_json(msg='boto3 and botocore are required for this module')

    region, ec2_url, aws_connect_params = get_aws_connection_info(module, boto3=True)

    try:
        connection = boto3_conn(module, conn_type='client', resource='autoscaling',
                                region=region, endpoint=ec2_url, **aws_connect_params)
    except (botocore.exceptions.NoCredentialsError, botocore.exceptions.ProfileNotFound) as e:
        module.fail_json(msg="Can't authorize connection. Check your credentials and profile.",
                         exceptions=traceback.format_exc(), **camel_dict_to_snake_dict(e.response))

    state = module.params.get('state')
    if state == 'present':
        create_scaling_policy(connection, module)
    elif state == 'absent':
        delete_scaling_policy(connection, module)


if __name__ == '__main__':
    main()
