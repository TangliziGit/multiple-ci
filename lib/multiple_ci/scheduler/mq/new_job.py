import json
import logging
import os.path
import time
import uuid

import yaml

from multiple_ci.utils import jobs
from multiple_ci.utils import git
from multiple_ci.model.plan_stage import PlanState

def handle_new_job(es, lkp_src, upstream_name):
    def extract_config(commands):
        config = {
            'id': 'none',
            'name': 'none',
            'PKGBUILD': 'none',
            'repository': 'none',
        }

        for cmd in commands.split(' '):
            if cmd == '': continue
            if '=' not in cmd: continue
            key, value = cmd.split('=')

            if key in config:
                config[key] = value
        return config

    def handle(ch, method, properties, arg):
        """
        :param arg: the configuration to generate a new plan, example {
          "commands": "name=hello-world PKGBUILD=... repository=... hello-world.yaml",
        }
        """

        arg = json.loads(arg.decode('utf-8'))
        logging.info(f'received job config: args={arg}')

        # submit the job
        commands = arg.get('commands', '')
        config = extract_config(commands)
        job = jobs.generate_job(commands, config, 'none', lkp_src)
        es.index(index='job', id=job['id'], document=job)

    return handle
