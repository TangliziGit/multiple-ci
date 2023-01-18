#!/bin/env python
import logging
import click

from multiple_ci.scanner import scanner
from multiple_ci.utils import caches
from multiple_ci.config import config

@click.command()
@click.option('--redis-host', default=config.DEFAULT_REDIS_HOST, help='redis host')
@click.option('--redis-port', default=config.DEFAULT_REDIS_PORT, help='redis prt')
@click.option('--redis-db', default=config.DEFAULT_REDIS_DB, help='redis db to store metas')
@click.option('--mq-host', default=config.DEFAULT_MQ_HOST, help='AMQP message queue host')
@click.option('--upstream-url', default=config.DEFAULT_UPSTREAM_URL, help='the upstream repo url')
@click.option('--debug', default=None, help='send a repo without checker just for debug')
def main(redis_host, redis_port, redis_db, mq_host, upstream_url, debug):
    LOG_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    caches.CacheManager.init(redis_host, redis_port, redis_db)

    if debug is not None:
        scanner.Scanner(mq_host, upstream_url=upstream_url).send(debug)
    else:
        s = scanner.Scanner(mq_host, upstream_url=upstream_url)
        s.init()
        s.scan()
