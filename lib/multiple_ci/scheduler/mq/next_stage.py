import logging
import json

from multiple_ci.utils import jobs

def handle_next_stage(es, notification_publisher, lkp_src):
    def handle(ch, method, properties, arg):
        """
        :param arg: current stage argument, example {
          "plan": "c1d1d2ac-d7e8-4bc2-9803-d5aadaeb4cc6",
          "current_stage": "build"
        }
        """
        arg = json.loads(arg.decode('utf-8'))
        plan = es.get(index='plan', id=arg['plan'])['_source']
        stages = plan['stages']
        stage_idx = next(idx for idx, stage in enumerate(stages)\
                         if stage['name'] == arg['current_stage'])

        if stage_idx+1 >= len(stages):
            logging.debug(f'no residual stage: plan_id={plan["id"]}, '
                          f'current_stage={arg["current_stage"]}, stage_idx={stage_idx}')
            notification_publisher.publish_dict({
                'type': 'success',
                'plan': plan['id'],
            })
        else:
            stage = stages[stage_idx+1]
            job_list = []
            for command in stage['commands']:
                job = jobs.generate_job(command, plan, stage['name'], lkp_src)
                stage['jobs'].append(job['id'])
                job_list.append(job)

            # NOTE: plan should be created before job, since /boot.ipxe will change plan stage state
            es.index(index='plan', id=plan['id'], document=plan)
            for job in job_list:
                es.index(index='job', id=job['id'], document=job)

    return handle
