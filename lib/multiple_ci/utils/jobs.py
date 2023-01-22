import uuid
import logging
import os.path
import subprocess
import pathlib

import yaml

from multiple_ci.config import config
from multiple_ci.model import job_state


def merge_yaml(commands, lkp_src):
    def read_yaml(yaml_name):
        yaml_path = list(pathlib.Path(lkp_src).rglob(cmd))
        if len(yaml_path) == 0:
            logging.warning(f'no such yaml file: yaml_name={yaml_name}')
            return {}

        if len(yaml_path) > 1:
            logging.warning(f'ambiguous yaml files: yaml_name={yaml_name}, path={yaml_path}')
            return {}

        with open(yaml_path[0]) as f:
            return yaml.load(f, Loader=yaml.FullLoader)

    content = {}
    for cmd in commands.reverse():
        if '=' in cmd:
            k, v = cmd.split('=')
            content = content | {k: v}
        elif '.yaml' in cmd or '.yml' in cmd:
            content = content | read_yaml(cmd)
        else:
            logging.warning(f'unknown command dropped: cmd={cmd}')
    return content

def create_job_package(job, mci_home, lkp_src):
    """
    Generate job directory via lkp-tests script `create-job-cpio.sh` like below:
    job_dir/job_id
    ├── job.cgz
    ├── job.sh
    └── job.yaml
    """
    directory = os.path.join(mci_home, 'job', job['id'])
    os.mkdir(directory)
    job_yaml = os.path.join(directory, 'job.yaml')
    with open(job_yaml, 'w') as f:
        yaml.dump(job, f)

    script_path = os.path.join(lkp_src, 'sbin', 'create-job-cpio.sh')
    cmd = f'{script_path} {job_yaml}'
    env = os.environ.copy()
    env['LKP_SRC'] = lkp_src
    subprocess.run(cmd.split(" "), env=env)

def get_result_stats(job_id, lkp_src):
    result_directory = os.path.join('/srv/result', job_id, 'result')
    script_path = os.path.join(lkp_src, 'sbin', 'result2stats')
    cmd = f'{script_path} {result_directory}'
    env = os.environ.copy()
    env['LKP_SRC'] = lkp_src
    subprocess.run(cmd.split(" "), env=env)

def generate_lkp_initramfs(kernel_path, lkp_src):
    path = pathlib.Path(kernel_path)
    version = '-'.join(path.name.split('-')[1:])
    modules_path = path.parent.parent.joinpath('lib', 'modules', version)

    script_path = os.path.join(lkp_src, 'sbin', 'mci', 'gen-initramfs.sh')
    cmd = f'{script_path} {modules_path}'
    subprocess.run(cmd.split(" "))

    return kernel_path.replace('vmlinuz', 'initramfs.lkp') + '.img'

# FIXME: check if job valid
# - stage name should not be duplicated
# - os, os_arch, os_version, os_mount should be supported ones
def generate_job(command, plan, stage_name, lkp_src):
    command = [x for x in command.split(" ") if x != '']
    job = merge_yaml(command, lkp_src)
    if job is None:
        logging.warning(f'fail to handle none job: command={command}')
        return None

    # set defaults and store it into ES
    job['os'] = job.get('os', 'centos')
    job['os_arch'] = job.get('os_arch', 'x86_64')
    job['os_mount'] = job.get('os_mount', 'nfs')
    job['os_version'] = job.get('os_version', '7')

    job['id'] = uuid.uuid4()
    job['plan'] = plan['id']
    job['stage'] = stage_name
    job['state'] = job_state.JobState.waiting.name
    job['priority'] = 0
    job['repository'] = plan['repository']
    job['PKGBUILD'] = plan['PKGBUILD']

    job['result_service'] = 'raw_upload'
    job['RESULT_ROOT'] = '/result'
    job['LKP_SERVER'] = config.LKP_SERVER
    return job