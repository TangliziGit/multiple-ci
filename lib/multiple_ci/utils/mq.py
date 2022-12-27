import json
import pika


class MQPublisher:
    def __init__(self, host, queue, username='root', password='123456'):
        self.queue = queue
        credentials = pika.PlainCredentials(username=username, password=password)
        parameters = pika.ConnectionParameters(host=host, credentials=credentials)
        self.connection = pika.BlockingConnection(parameters=parameters)
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=queue)

    def publish(self, body):
        self.channel.basic_publish(exchange='', routing_key=self.queue, body=body)

    def publish_dict(self, body):
        self.publish(json.dumps(body))

    def close(self):
        self.connection.close()


class MQConsumer:
    def __init__(self, host, queue, username='root', password='123456'):
        self.queue = queue
        credentials = pika.PlainCredentials(username=username, password=password)
        parameters = pika.ConnectionParameters(host=host, credentials=credentials)
        self.connection = pika.BlockingConnection(parameters=parameters)
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=queue)

    def consume(self, callback):
        self.channel.basic_consume(queue=self.queue, on_message_callback=callback, auto_ack=True)
        self.channel.start_consuming()

    def close(self):
        self.connection.close()
