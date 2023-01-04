import logging
import os.path
import subprocess
import uuid
import pathlib

import yaml

def generate_id(job):
    job['id'] = uuid.uuid4()
    return job

def merge_yaml(kvs, yaml_name, lkp_src):
    yaml_path = list(pathlib.Path(lkp_src).rglob(yaml_name))
    if len(yaml_path) == 0:
        logging.warning(f'no such yaml file: yaml_name={yaml_name}')
        return None

    if len(yaml_path) > 1:
        logging.warning(f'ambiguous yaml files: yaml_name={yaml_name}, path={yaml_path}')
        return None

    with open(yaml_path[0]) as f:
        content = yaml.load(f, Loader=yaml.FullLoader)
        for kv in kvs:
            if len(kv) == 0: continue
            k, v = kv.split('=')
            content[k] = v
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