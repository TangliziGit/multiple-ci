import logging

import elasticsearch

from multiple_ci.utils import jobs
from multiple_ci.model import job_status

def handle_submit(lkp_src, job_dir, es_endpoint):
    es = elasticsearch.Elasticsearch(es_endpoint)
    def handle(ch, method, properties, job_config):
        logging.debug(f'received job config: config={job_config}')

        # merge command key value pairs
        command = job_config['defaults']['submit'][0]['command']
        job = jobs.merge_yaml(command[:-1], command[-1])

        # generate job.cgz and store it into TFTP
        jobs.generate_id(job)
        jobs.create_job_package(job, job_dir, lkp_src)

        # store it into ES
        job['status'] = job_status.JobStatus.WAITING.name
        es.index(index='jobs', id=job['id'], document=job)

        # TODO: send into arch queue

    return handle