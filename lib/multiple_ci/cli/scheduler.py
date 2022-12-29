#!/bin/env python
import logging
import click

from multiple_ci.scheduler import scheduler
from multiple_ci.config import config

@click.command()
@click.option('--port', default=config.DEFAULT_SCHEDULER_WEB_PORT, help='scheduler web port')
@click.option('--mq-host', default=config.DEFAULT_MQ_HOST, help='AMQP message queue host')
@click.option('--es-endpoint', default=config.DEFAULT_ES_ENDPOINT, help='ES host and port')
@click.option('--lkp-src', default=config.DEFAULT_LKP_SRC, help='the lkp-tests source path')
@click.option('--job-dir', default=config.DEFAULT_JOB_DIR, help='the directory to store jobs yaml and scripts')
def main(port, mq_host, es_endpoint, lkp_src, job_dir):
    LOG_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)

    scheduler.Scheduler(port, mq_host, es_endpoint, lkp_src, job_dir).run()
