import json
import yaml
import logging
import smtplib
from email.mime.text import MIMEText
from email.header import Header

from multiple_ci.config import config

class EmailSender:
    def __init__(self):
        pass

    def send(self, target, argument):
        receivers = [target]
        content = yaml.dump(argument)

        message = MIMEText(content, 'plain', 'utf-8')
        message['From'] = Header("multiple-ci", 'utf-8')
        message['To'] = Header("multiple-ci maintainer group", 'utf-8')
        message['Subject'] = Header(f'[multiple-ci] job result', 'utf-8')

        smtpObj = smtplib.SMTP()
        smtpObj.connect(config.EMAIL_HOST, 25)
        smtpObj.login(config.EMAIL_USERNAME, config.EMAIL_PASSWORD)
        smtpObj.sendmail(config.EMAIL_SENDER, receivers, message.as_string())


class FileSender:
    def __init__(self):
        pass

    def send(self, target, argument):
        logging.info(f"target={target}, arg={argument}")
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