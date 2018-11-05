#!/usr/bin/env python3

import re, sys, subprocess

import yaml
# Make yaml dump None value as blank instead of 'null'
def represent_none(self, _):
    return self.represent_scalar('tag:yaml.org,2002:null', '')
yaml.add_representer(type(None), represent_none)


def run_cmd(cmd,sendtxt=None, working_dir=".", args=[], shell=False, DEBUG=False, shlex=False):
    if DEBUG:
        cmd2 = re.sub('root:([^\s])', 'root:xxxxx', cmd) # suppress the root password printout
        print(cmd2)
    if sys.platform == "win32":
        args = cmd
    else:
        if shlex:
            import shlex
            args = shlex.split(cmd)
        else:
            args = cmd

    popen = subprocess.Popen(
            args,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            cwd=working_dir
        )
    if sendtxt: output, err = popen.communicate(bytearray(sendtxt, 'utf-8'))
    else: output, err = popen.communicate()
    code = popen.returncode
    if not code == 0 or DEBUG:
        output = "Command string: '%s'\n\n%s" % (cmd, output)
    return (output, code, err)

def yaml_load(file_path):
    return yaml.load(open(file_path,"r").read())

def yaml_save(file_path, python_object):
    content = yaml.dump(python_object, default_flow_style=False)
    return open(file_path,"w").write(content)
