import http
import logging

import elasticsearch

from multiple_ci.scheduler.web.util import BaseHandler
from multiple_ci.model.machine_state import MachineState
from multiple_ci.model.job_state import JobState


class PostRunHandler(BaseHandler):
    def initialize(self, es, mq_publisher):
        self.es = es
        self.publisher = mq_publisher

    def get(self):
        job_file = self.get_argument('job_file')
        job_id = self.get_argument('job_id')
        logging.info(f'post run: job_file={job_file}, job_id={job_id}')

        result = self.es.search(index='machine', query={'match': {'job_id': job_id}})['hits']['hits']
        if len(result) == 0:
            self.err(http.HTTPStatus.NOT_FOUND, f'no such machine: job_id={job_id}')
            return
        if len(result) > 1:
            self.err(http.HTTPStatus.INTERNAL_SERVER_ERROR,
                     f'duplicated machine: job_id={job_id}, machines={result}')
            return

        job = self.es.get(index='job', id=job_id)['_source']
        machine = result[0]['_source'] | {'state': MachineState.idle.name}
        job = job | {'state': JobState.done.name}

        # FIXME: atomic update
        self.es.index(index='job', id=job_id, document=job)
        self.es.index(index='machine', id=machine['mac'], document=machine)

        self.publisher.publish(job_id)
        self.ok()


class JobVarHandler(BaseHandler):
    def initialize(self, es):
        self.es = es

    def get(self):
        args = dict(self.request.arguments)
        job_file = self.get_argument('job_file')
        job_id = self.get_argument('job_id')
        logging.info(f'job file: job_file={job_file}, job_id={job_id}, args={args}')

        del args['job_file']
        del args['job_id']
        if 'job_state' in args:
            args['status'] = args.pop('job_state')
        for k, v in args.items():
            args[k] = v[-1].decode('utf-8')

        job = self.es.get(index='job', id=job_id)['_source']
        job = job | args
        self.es.index(index='job', id=job_id, document=job)
        self.ok(job)


class TestBoxHandler(BaseHandler):
    def initialize(self, es):
        self.es = es

    def get(self):
        name = self.get_argument('tbox_name')
        status = self.get_argument('tbox_state')
        mac = self.get_argument('mac')
        ip = self.get_argument('ip')
        job_id = self.get_argument('job_id')
        logging.info(f'test box: name={name}, status={status}, mac={mac}, ip={ip}, job_id={job_id}')

        machine = self.es.get(index='machine', id=mac)['_source']
        machine = machine | {
            'name': name,
            'status': status,
            'mac': mac,
            'ip': ip,
            'job_id': job_id
        }

        self.es.index(index='machine', id=mac, document=machine)
        self.ok(machine)

class PlanKernelHandler(BaseHandler):
    def initialize(self, es):
        self.es = es

    def get(self):
        plan_id = self.get_argument('plan_id')
        path = self.get_argument('path')
        logging.info(f'set plan kernel: plan_id={plan_id}, path={path}')

        while True:
            result = self.es.get(index='plan', id=plan_id)
            plan = result['_source']
            plan['config']['kernel'] = path
            try:
                self.es.index(index='plan', id=plan_id, document=plan,
                              if_primary_term=result['_primary_term'], if_seq_no=result['_seq_no'])
            except elasticsearch.ConflictError as err:
                logging.warning(f'retry to handle result since concurrency control failed: err={err}')
                continue
            else:
                logging.debug(f'result dealt successfully')
                break
        self.ok()

class PlanPackagesHandler(BaseHandler):
    def initialize(self, es):
        self.es = es

    def get(self):
        plan_id = self.get_argument('plan_id')
        path = self.get_argument('path')
        logging.info(f'set plan packages: plan_id={plan_id}, path={path}')

        while True:
            result = self.es.get(index='plan', id=plan_id)
            plan = result['_source']
            if 'packages' not in plan['config']:
                plan['config']['packages'] = []
            plan['config']['packages'].append(path)
            try:
                self.es.index(index='plan', id=plan_id, document=plan,
                              if_primary_term=result['_primary_term'], if_seq_no=result['_seq_no'])
            except elasticsearch.ConflictError as err:
                logging.warning(f'retry to handle result since concurrency control failed: err={err}')
                continue
            else:
                logging.debug(f'result dealt successfully')
                break
        self.ok()
