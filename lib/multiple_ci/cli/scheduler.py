#!/bin/env python
import logging
import click

from multiple_ci.scheduler import scheduler
from multiple_ci.config import config
from multiple_ci.utils import caches


@click.command()
@click.option('--port', default=config.DEFAULT_SCHEDULER_WEB_PORT, help='scheduler web port')
@click.option('--mq-host', default=config.DEFAULT_MQ_HOST, help='AMQP message queue host')
@click.option('--es-endpoint', default=config.DEFAULT_ES_ENDPOINT, help='ES host and port')
@click.option('--lkp-src', default=config.DEFAULT_LKP_SRC, help='the lkp-tests source path')
@click.option('--mci-home', default=config.DEFAULT_MULTIPLE_CI_HOME, help='multiple-ci home directory')
@click.option('--upstream-url', default=config.DEFAULT_UPSTREAM_URL, help='the upstream repo url')
@click.option('--redis-host', default=config.DEFAULT_REDIS_HOST, help='redis host')
@click.option('--redis-port', default=config.DEFAULT_REDIS_PORT, help='redis port')
@click.option('--redis-db', default=config.DEFAULT_REDIS_DB, help='redis db to store metas')
def main(port, mq_host, es_endpoint, lkp_src, mci_home, upstream_url, redis_host, redis_port, redis_db):
    LOG_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    caches.CacheManager.init(redis_host, redis_port, redis_db)

    upstream_name = upstream_url.split('/')[-1]
    scheduler.Scheduler(port, mq_host, es_endpoint, lkp_src, mci_home, upstream_name).run()
