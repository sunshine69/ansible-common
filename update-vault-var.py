#!/usr/bin/env python
"""Origin from here https://github.com/andrunah/ansible-vault-variable-updater
Open a yml file with inline vault with old vault pass file and dump into a new
file with new vault encryption with new-vault pass file

Still complex htings to do, we can load and decrypt teh yml file but to
reencrypt back we need a way to devetxt variables which is vaulted and encrypt
back. No time for now, maybe in the future ...

status: TODO

"""
import codecs
import yaml
import sys
from ansible.parsing import vault
from ansible.parsing.dataloader import DataLoader
from ansible.parsing.yaml import objects
from ansible.parsing.yaml.dumper import AnsibleDumper
from ansible.parsing.yaml.loader import AnsibleLoader


def main():
    vault_file = sys.argv[1]
    new_vault_file = sys.argv[2]
    in_file = sys.argv[3]

    target_env = 'test'
    external_system_name = 'blabla'

    # Load vault password and prepare secrets for decryption
    loader = DataLoader()
    secret = vault.get_file_vault_secret(filename=vault_file, loader=loader)
    secret.load()
    vault_secrets = [('default', secret)]
    _vault = vault.VaultLib(vault_secrets)

    new_loader = DataLoader()
    new_secret = vault.get_file_vault_secret(filename=new_vault_file, loader=new_loader)
    new_secret.load()
    new_vault_secrets = [('default', new_secret)]
    _new_vault = vault.VaultLib(new_vault_secrets)

    # Load encrypted yml for processing
    with codecs.open(in_file, 'r', encoding='utf-8') as f:
        loaded_yaml = AnsibleLoader(f, vault_secrets=_vault.secrets).get_single_data()

    # Modify yml with new encrypted values
    new_encrypted_variable = objects.AnsibleVaultEncryptedUnicode.from_plaintext(external_system_password, _new_vault, new_vault_secrets[0][1])

    loaded_yaml[target_env]['credentials'][external_system_name]['password'] = new_encrypted_variable

    # Write a new encrypted yml
    with open("%s.new" % argv[1], 'wb') as fd:
        yaml.dump(loaded_yaml, fd, Dumper=AnsibleDumper, encoding=None, default_flow_style=False)

    print(loaded_yaml)


if __name__ == '__main__':
    main()
