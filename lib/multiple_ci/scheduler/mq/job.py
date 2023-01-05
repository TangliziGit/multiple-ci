import json
import logging

from multiple_ci.config import config
from multiple_ci.utils import jobs
from multiple_ci.model import job_status

def handle_submit(es, lkp_src):
    def handle(ch, method, properties, job_config):
        job_config = json.loads(job_config.decode('utf-8'))
        logging.info(f'received job config: config={job_config}')

        # merge command key value pairs
        command = job_config['defaults']['submit'][0]['command'].split(" ")
        command = [x for x in command if x != '']
        job = jobs.merge_yaml(command[:-1], command[-1], lkp_src)
        if job is None:
            logging.warning(f'fail to handle none job: command={command}')
            return

        # set defaults and store it into ES
        job = jobs.generate_id(job)
        job['status'] = job_status.JobStatus.waiting.name
        job['os_arch'] = 'x86_64' # job.get('os_arch', 'x86_64')
        job['priority'] = 0

        job['os_mount'] = 'nfs'
        job['result_service'] = 'raw_upload'
        job['RESULT_ROOT'] = '/result'
        job['LKP_SERVER'] = config.LKP_SERVER
        es.index(index='job', id=job['id'], document=job)

    return handle