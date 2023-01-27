import json
import logging
import os.path
import subprocess
import uuid

import yaml

from multiple_ci.utils import jobs

def handle_new_plan(es, lkp_src, upstream_name):
    def handle(ch, method, properties, arg):
        """
        :param arg: the configuration to generate a new plan, example {
          "time": 1673688015376516900,
          "name": "hello-world",
          "commit": {
              "meta": "7d5ca10db5bc34ed939c9ad87a64279a20610b06",
              "repo": "7d5ca10db5bc34ed939c9ad87a64279a20610b06"
          },
          "meta": {
              "repository": "",
              "PKGBUILD": "",
              "notify": {
                "email": [ "xxx@yyy.zzz" ]
              }
          }
        }
        """

        arg = json.loads(arg.decode('utf-8'))
        logging.info(f'received plan config: args={arg}')

        # get plan.yaml with specific meta commit id
        upstream_path = os.path.join('/srv/git/', upstream_name)
        cmd = f'git -C {upstream_path} reset --hard {arg["commit"]["meta"]}'
        # FIXME: concurrency control & exception check & atomic rollback
        subprocess.run(cmd.split(" "))
        plan_path = os.path.join(upstream_path, arg['name'][0], arg['name'], 'plan.yaml')
        with open(plan_path, 'r') as plan_file:
            plan_content = yaml.load(plan_file, Loader=yaml.FullLoader)

        # generate the new plan
        plan = {
            "id": uuid.uuid4(),
            "name": arg['name'],
            "commit": {
                "meta": arg['commit']['meta'],
                "repo": arg['commit']['repo'],
            },
            "repository": arg['meta']['repository'],
            "PKGBUILD": arg['meta'].get('PKGBUILD', None),
            "notify": arg['meta'].get('notify', {}),
            "stages": [],
            "config": {
                "kernel": '',
                "initramfs": '',
                "packages": []
            }
        }

        for stage in plan_content['stages']:
            stage_name = list(stage.keys())[0]
            commands = stage[stage_name]
            plan['stages'].append({
                'name': stage_name,
                'jobs': [],
                'commands': commands,
                'residual': len(commands),
                'state': 'waiting'
            })

        es.index(index='plan', id=plan['id'], document=plan)

        # submit first stage jobs
        for command in plan['stages'][0]['commands']:
            job = jobs.generate_job(command, plan, plan['stages'][0]['name'], lkp_src)
            plan['stages'][0]['jobs'].append(job['id'])
            es.index(index='job', id=job['id'], document=job)
        es.index(index='plan', id=plan['id'], document=plan)

    return handle