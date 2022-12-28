import os.path
import subprocess
import uuid

import yaml

def generate_id(job):
    job['id'] = uuid.uuid4()

def merge_yaml(kvs, yaml_path):
    with open(yaml_path) as f:
        content = yaml.load(f, Loader=yaml.FullLoader)
        for k, v in kvs:
            content[k] = v
    return content

def create_job_package(job, job_dir, lkp_src):
    """
    Generate job directory via lkp-tests script `create-job-cpio.sh` like below:
    job_dir/job_id
    ├── job.cgz
    ├── job.sh
    └── job.yaml
    """
    directory = os.path.join(job_dir, job['id'])
    job_yaml = os.path.join(directory, 'job.yaml')
    with open(job_yaml) as f:
        yaml.dump(f, job)

    script_path = os.path.join(lkp_src, 'sbin', 'create-job-cpio.sh')
    cmd = f'LKP_SRC={lkp_src} {script_path} {job_yaml}'
    subprocess.run(cmd)