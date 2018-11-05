# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = """
    lookup: kms
    version_added: "2.5"
    short_description: retrieve values as a result of encrypt/decrypt action from KMS service on AWS
    requirements:
      - boto3
    description:
      - "retrieve values as a result of encrypt/decrypt action from KMS service on AWS"
    options:
      region:
        description: AWS region
      profile_name:
        description: AWS profile to use for authentication
        env:
          - name: AWS_PROFILE
      aws_access_key_id:
        description: AWS access key ID
        env:
          - name: AWS_ACCESS_KEY_ID
      aws_secret_access_key:
        description: AWS access key
        env:
          - name: AWS_SECRET_ACCESS_KEY
      aws_session_token:
        description: AWS session token
        env:
          - name: AWS_SESSION_TOKEN
"""

EXAMPLES = """
- name: "Test kms lookup plugin"
  debug: msg="Credstash lookup! {{ lookup('kms', 'enc', 'my-password') }}"

- name: "Test kms lookup plugin -- get the password with a context defined here"
  debug: msg="{{ lookup('kms', 'dec', 'some-encrypted-password', context=dict(app='my_app', environment='production')) }}"
"""

RETURN = """
  _raw:
    description:
      - value(s) as the result of kms encrypt/decrypt
"""

import boto3
import base64
import os

from ansible.plugins.lookup import LookupBase


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        '''
            :param terms: a list of plugin options
                          e.g. ['enc', 'input_data']
            :param variables: config variables
            :param kwargs: profile='profile_name', region='aws_region'
            :return The value of the action result or None
        '''

        region = kwargs.pop('region', None)
        profile_name = kwargs.pop('profile', os.getenv('AWS_PROFILE', None))
        if profile_name.startswith('__omit_place_holder__'):
            profile_name = None
        aws_access_key_id = kwargs.pop('aws_access_key_id', os.getenv('AWS_ACCESS_KEY_ID', None))
        aws_secret_access_key = kwargs.pop('aws_secret_access_key', os.getenv('AWS_SECRET_ACCESS_KEY', None))
        aws_session_token = kwargs.pop('aws_session_token', os.getenv('AWS_SESSION_TOKEN', None))
        kwargs_pass = {'profile_name': profile_name, 'aws_access_key_id': aws_access_key_id,
                       'aws_secret_access_key': aws_secret_access_key, 'aws_session_token': aws_session_token}

        context = kwargs.pop('context', {})
        key, action, plaintext = terms

        kms = boto3.session.Session(**kwargs_pass).client('kms', region_name=region)

        if action in ['enc', 'encrypt']:
            response = kms.encrypt( \
                KeyId=key, \
                Plaintext=plaintext, \
                EncryptionContext=context)

            if 'CiphertextBlob' in response:
                return [base64.b64encode(response['CiphertextBlob'])]
            else:
                raise Exception("Encryption Failed.")

        elif action in ['dec', 'decrypt']:
            response = kms.decrypt( \
                CiphertextBlob=base64.b64decode(plaintext), \
                EncryptionContext=context)

            if 'Plaintext' in response:
                return [response['Plaintext']]
            else:
                raise Exception("Decryption failed.")
        else:
            return ["Unknown action"]
