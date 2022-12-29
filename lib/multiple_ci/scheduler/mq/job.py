import logging

from multiple_ci.utils import jobs
from multiple_ci.model import job_status

def handle_submit(es):
    def handle(ch, method, properties, job_config):
        logging.debug(f'received job config: config={job_config}')

        # merge command key value pairs
        command = job_config['defaults']['submit'][0]['command']
        job = jobs.merge_yaml(command[:-1], command[-1])

        # store it into ES
        job['status'] = job_status.JobStatus.waiting.name
        job['arch'] = job.get('arch', 'x86_64')
        job['priority'] = 0
        es.index(index='jobs', id=job['id'], document=job)

    return handle