#!/usr/bin/python3

# This is a frustration of the limitation - no 'update' option of the current
# ansible-galaxy command.

import os
import re
import sys

from tools.helper import *

import yaml

def update_requirement_file():
    """ Update all version of module in the requirements file to the latest minor version tag from upstream.
        For example if there is a tag v1.5 in the galaxy repo and the current
        on if v1.4 then it will be updated to 1.5.
        It wont update if the remote has tag v2.0.
    """
    print("To be implemented")

def delete_local():
    req = yaml.load(open('requirements.yml','r').read(), Loader=yaml.FullLoader)
    for role_from_requirement in req:
        ver_from_requirements = role_from_requirement['version']
        try:
            role_name = role_from_requirement['name']
        except KeyError as e:
            role_name = role_from_requirement['src'].split('/')[-1].split('.')[0]
            role_from_requirement['name'] = role_name

        print("going to delete roles/%s" % role_name)
        os.system("rm -rf roles/%s" % role_name)



def update_galaxy_role():
    """Do the update galaxy role if the version as of current is not match with
    version specified in the requirements file.
    """

    req = yaml.load(open('requirements.yml','r').read(), Loader=yaml.FullLoader)

    output, c, _ = run_cmd('ansible-galaxy list', shlex=True)

    galaxy_list_role_lookup = {}

    ptn = re.compile(r'^- ([^,\s]+), ([^\s]+)$')

    for line in output.splitlines():
        m = ptn.search(line.decode('utf-8'))
        if m:
            galaxy_list_role_lookup[m.group(1)] = m.group(2)

    list_of_roles_need_to_update = []

    for role_from_requirement in req:
        ver_from_requirements = role_from_requirement['version']
        try:
            role_name = role_from_requirement['name']
        except KeyError as e:
            role_name = role_from_requirement['src'].split('/')[-1].split('.')[0]
            role_from_requirement['name'] = role_name

        try:
            ver_from_galaxy_role = galaxy_list_role_lookup[role_name]
        except KeyError as e:
            list_of_roles_need_to_update.append({ 'name': role_name, 'remove': False, 'ver': 'N/A', 'newver': ver_from_requirements })
            continue

        # If match the pattern we force to update.
        role_ver_pattern_force_update = re.compile('^test[^\s]+$')
        if ver_from_requirements != ver_from_galaxy_role or role_ver_pattern_force_update.match(ver_from_requirements):
            list_of_roles_need_to_update.append({ 'name': role_from_requirement['name'], 'remove': True, 'ver': ver_from_galaxy_role, 'newver': ver_from_requirements })

    for role_need_to_update in list_of_roles_need_to_update:
        print("Updating role %s - from %s => %s" % (role_need_to_update['name'], role_need_to_update['ver'], role_need_to_update['newver'] ) )

        if role_need_to_update['remove']:
            o, c, e = run_cmd('ansible-galaxy remove %s' % role_need_to_update['name'], shlex=True)

        o, c, e = run_cmd('ansible-galaxy install -r requirements.yml %s' % role_need_to_update['name'], shlex=True)
        if c != 0:
            print(c, e)

def main():
    command = ""

    try:
        command = sys.argv[1]
    except:
        pass

    if command == 'autoupdate':
        update_requirement_file()
    elif command == 'delete':
        delete_local()
    else:
        update_galaxy_role()

if __name__ == '__main__':
    main()
