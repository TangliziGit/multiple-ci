import logging
import os.path
import subprocess
import uuid
import pathlib

import yaml

def generate_id(job):
    job['id'] = uuid.uuid4()
    return job

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
    for cmd in commands:
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