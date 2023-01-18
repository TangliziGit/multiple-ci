import logging
import threading

import elasticsearch

from multiple_ci.config import config
from multiple_ci.model.machine_state import MachineState

class Monitor:
    def __init__(self, es):
        self.mac2timer = {}
        self.mac2socket = {}
        self.socket2mac = {}
        self.es = es

    def close_socket(self, socket):
        self.mac2socket[self.socket2mac[socket]] = None
        del self.socket2mac[socket]

    def send(self, message, socket=None, mac=None):
        if socket is not None:
            socket.write_message(message)
            return True

        if mac is not None and mac in self.mac2socket:
            self.mac2socket[mac].write_message(message)
            return True
        return False

    def bind(self, socket, mac):
        self.socket2mac[socket] = mac
        self.mac2socket[mac] = socket

    def pong(self, socket=None, mac=None):
        if socket is not None:
            self.__pong_via_socket(socket)
        if mac is not None:
            self.__pong_via_mac(mac)

    def __pong_via_socket(self, socket):
        if socket not in self.socket2mac:
            return

        mac = self.socket2mac[socket]
        if mac not in self.mac2timer:
            self.mac2timer[mac] = Timer(self.down_callback(mac))
            self.mac2socket[mac] = socket
        else:
            self.mac2timer[mac].reset()
            self.mac2socket[mac] = socket

    def __pong_via_mac(self, mac):
        if mac not in self.mac2timer:
            self.mac2timer[mac] = Timer(self.down_callback(mac))
            self.mac2socket[mac] = None
        else:
            self.mac2timer[mac].reset()

    def down_callback(self, mac):
        def callback():
            logging.warning(f'test machine has been down: mac={mac}')
            while True:
                try:
                    result = self.es.get(index='machine', id=mac)
                    machine = result['_source']
                    machine['state'] = MachineState.down.name
                    self.es.index(index='machine', id=mac, document=machine,
                          if_primary_term=result['_primary_term'], if_seq_no=result['_seq_no'])
                except elasticsearch.ConflictError as err:
                    logging.warning(f'retry to handle result since concurrency control failed: err={err}')
                else:
                    logging.debug(f'result dealt successfully')
                    break
        return callback


# TODO: one thread for one machine. does it need be optimized?
class Timer:
    def __init__(self, callback, interval=config.MACHINE_DOWN_TIMER_SEC):
        self.function = callback
        self.interval = interval
        self.timer = threading.Timer(interval, callback)
        self.timer.start()

    def reset(self):
        self.timer.cancel()
        self.timer = threading.Timer(self.interval, self.function)
        self.timer.start()

    def close(self):
        self.timer.cancel()