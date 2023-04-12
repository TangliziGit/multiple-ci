import os
import time

import yaml

from multiple_ci.model.plan_config import PlanConfig
from multiple_ci.config import config
from multiple_ci.utils import git


def get_commit_id(repo_name):
    repo_path=os.path.join("/srv/git", repo_name)
    commit_id = git.run('log --pretty=format:"%H" -n 1', repo_path=repo_path)
    return commit_id[1:-1]

def iterator(upstream_path):
    for ch in map(chr, range(ord('a'), ord('z') + 1)):
        path = os.path.join(upstream_path, ch)
        for root, dirs, files in os.walk(path):
            for d in dirs:
                yield os.path.join(root, d), d

def generate_plan_config(directory, name):
    meta_path = os.path.join(directory, 'meta.yaml')
    plan_path = os.path.join(directory, 'plan.yaml')
    if not os.path.exists(meta_path) or not os.path.exists(plan_path):
        return None

    with open(meta_path) as meta_file:
        meta = yaml.load(meta_file, Loader=yaml.FullLoader)
        if 'notify' not in meta:
            meta['notify'] = {}

        repo_path = os.path.join("/srv/git", name)
        if not os.path.exists(repo_path):
            git.run(f'clone --depth 1 {meta["repository"]} {repo_path}')

        with open(plan_path) as plan_file:
            plan_config = {
                'time': time.time_ns(),
                'url': meta['repository'],
                'name': name,
                'dir': directory,
                'checker': meta.get('checker', 'commit-count'),
                'defaults': yaml.load(plan_file, Loader=yaml.FullLoader),
                'PKGBUILD': meta.get('PKGBUILD', None),
                'meta': meta,
            }
    return PlanConfig(plan_config)
