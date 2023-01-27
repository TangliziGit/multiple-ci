#!/bin/env python
import logging
import click

from multiple_ci.notifier import notifier
from multiple_ci.config import config

@click.command()
@click.option('--mq-host', default=config.DEFAULT_MQ_HOST, help='AMQP message queue host')
@click.option('--es-endpoint', default=config.DEFAULT_ES_ENDPOINT, help='ES host and port')
def main(mq_host, es_endpoint):
    LOG_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    notifier.Notifier(mq_host, es_endpoint).run()