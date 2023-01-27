import json
import logging


class EmailSender:
    def __init__(self):
        pass

    def send(self, target, argument):
        # TODO
        pass


class FileSender:
    def __init__(self):
        pass

    def send(self, target, argument):
        with open(target, 'w') as f:
            f.write(json.dumps(argument))


class WebhookSender:
    def __init__(self):
        pass

    def send(self, target, argument):
        # TODO
        pass


class SenderSelector:
    def __init__(self):
        self.senders = {
            'email': EmailSender(),
            'file': FileSender(),
            'webhook': WebhookSender(),
        }

    def get_sender(self, name):
        if name not in self.senders:
            logging.warning(f"no such sender: name={name}")
            return None
        return self.senders[name]