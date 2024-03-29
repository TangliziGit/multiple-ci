import logging
import os
import shutil
import threading

import elasticsearch

from multiple_ci.config import config
from multiple_ci.model.machine_state import MachineState
from multiple_ci.model.job_state import JobState

class Monitor:
    def __init__(self, es, mci_home, notification_publisher):
        self.mac2timer = {}
        self.mac2socket = {}
        self.socket2mac = {}
        self.es = es
        self.mci_home = mci_home
        self.notification_publisher = notification_publisher

    def init(self):
        machines = self.es.search(index='machine', query={'match_all': {}})['hits']['hits']
        machines = [m['_source'] for m in machines]
        for machine in machines:
            mac = machine['mac']
            arch = machine['arch']
            timeout = config.X86_64_MACHINE_DOWN_TIMER_SEC if arch == 'x86_64' else \
                config.AARCH64_MACHINE_DOWN_TIMER_SEC
            self.mac2timer[mac] = Timer(self.down_callback(mac), timeout)

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
        machine = self.es.get(index='machine', id=mac)['_source']
        machine['state'] = MachineState.busy.name
        self.es.index(index='machine', id=mac, document=machine)

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
            downtime_message = None
            while True:
                try:
                    machine_resp = self.es.get(index='machine', id=mac)
                    machine = machine_resp['_source']
                    machine['state'] = MachineState.down.name

                    self.es.index(index='machine', id=mac, document=machine,
                          if_primary_term=machine_resp['_primary_term'], if_seq_no=machine_resp['_seq_no'])

                    # NOTE: it is necessary to ensure atomic es update?
                    # No, because no matter whether the machine state update fails,
                    #   it will retry until succeeds and does not affect the correctness.

                    # NOTE: job field is empty only when machine.state equals idle
                    if machine['job'] != '':
                        job_resp = self.es.get(index='job', id=machine['job'])
                        job = job_resp['_source']
                        job['state'] = JobState.waiting.name
                        job['machine'] = ""
                        job['downtime'] = int(job['downtime']) + 1
                        if job['downtime'] >= config.DOWNTIME_COUNT:
                            downtime_message = {
                                'plan': job['plan'],
                                'type': 'system',
                                'arguments': [
                                    f'the downtime of the job {job["id"]} has reached the upper limit'
                                ]
                            }
                        shutil.rmtree(os.path.join(self.mci_home, 'job', job['id']))
                        self.es.index(index='job', id=job['id'], document=job,
                                      if_primary_term=job_resp['_primary_term'], if_seq_no=job_resp['_seq_no'])
                except elasticsearch.ConflictError as err:
                    logging.warning(f'retry to handle result since concurrency control failed: err={err}')
                else:
                    logging.debug(f'result dealt successfully')
                    logging.info(f'interrupted job has been restarted')
                    break

            if downtime_message is not None:
                self.notification_publisher.publish_dict(downtime_message)
        return callback


# TODO: one thread for one machine. does it need be optimized?
class Timer:
    def __init__(self, callback, interval=config.X86_64_MACHINE_DOWN_TIMER_SEC):
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