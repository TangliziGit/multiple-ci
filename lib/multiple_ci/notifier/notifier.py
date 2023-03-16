import json
import logging

import elasticsearch

from multiple_ci.utils.mq import MQConsumer
from multiple_ci.notifier.sender import SenderSelector


class NotificationHandler:
    def __init__(self, es):
        self.es = es
        self.sender_selector = SenderSelector()

    def handler(self):
        def handle(ch, method, properties, arg):
            """
            :param arg: the notification configuration, example {
              "type": "success | failure | system",
              "plan": "d616a42d-11aa-4107-97da-c366d6da8174",
              "arguments": [ "<job-id>" ]
            }
            """
            arg = json.loads(arg.decode('utf-8'))
            logging.info(f'send notifications: arg={arg}')
            plan = self.es.get(index='plan', id=arg['plan'])['_source']

            for sender_name, targets in plan['notify'].items():
                sender = self.sender_selector.get_sender(sender_name)
                for target in targets:
                    sender.send(target, arg)

        return handle


class Notifier:
    def __init__(self, mq_host, es_endpoint):
        self.consumer = MQConsumer(mq_host, 'notification')
        self.es = elasticsearch.Elasticsearch(es_endpoint)
        self.handler = NotificationHandler(self.es)

    def run(self):
        self.consumer.consume(self.handler.handler())