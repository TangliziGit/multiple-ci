#!/bin/env python
import logging
import click

from multiple_ci.analyzer import analyzer
from multiple_ci.config import config

@click.command()
@click.option('--mq-host', default=config.DEFAULT_MQ_HOST, help='AMQP message queue host')
@click.option('--lkp-src', default=config.DEFAULT_LKP_SRC, help='the lkp-tests source path')
@click.option('--es-endpoint', default=config.DEFAULT_ES_ENDPOINT, help='ES host and port')
@click.option('--scheduler-endpoint', default=config.DEFAULT_SCHEDULER_ENDPOINT, help='scheduler host and port')
def main(mq_host, lkp_src, es_endpoint, scheduler_endpoint):
    LOG_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    analyzer.ResultAnalyzer(mq_host, es_endpoint, scheduler_endpoint, lkp_src).run()