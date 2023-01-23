import logging

import tornado.websocket

class MonitorActionsHandler(tornado.websocket.WebSocketHandler):
    def data_received(self, chunk): pass
    def initialize(self, monitor):
        self.monitor = monitor

    def open(self):
        logging.info(f'new websocket connection set up')

    def on_close(self):
        self.monitor.close_socket(self)

    def on_message(self, message):
        """
        :param message: example: 'bind(mac)', 'reboot(job_id)', 'cmd(arg1,arg2)'
        """
        command = message.split('(')[0]
        arguments = message[len(command)+1:-1].split(',')
        match command:
            case 'bind':
                self.monitor.bind(self, arguments[0])
            case 'log':
                logging.info(f'log message received: mac={self.monitor.socket2mac[self]}, msg={arguments}')
            case _:
                logging.warning(f'no such command: command={command}, arguments={arguments}')

    def on_pong(self, data: bytes):
        logging.debug(f'heartbeat pong: mac={self.monitor.socket2mac.get(self, None)}')
        self.monitor.pong(self)
