import os
import time

import yaml


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
        with open(plan_path) as plan_file:
            plan_config = {
                'time': time.time_ns(),
                'url': meta['repository'],
                'dir': directory,
                'name': name,
                'checker': meta.get('checker', 'commit-count'),
                'defaults': yaml.load(plan_file, Loader=yaml.FullLoader),
                'PKGBUILD': meta.get('PKGBUILD', None)
            }
    return plan_config
