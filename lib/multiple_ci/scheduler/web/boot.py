import logging

import elasticsearch

from multiple_ci.model.job_state import JobState
from multiple_ci.model.stage_state import StageState
from multiple_ci.model.machine_state import MachineState
from multiple_ci.utils import jobs
from multiple_ci.scheduler.web.util import BaseHandler

ipxe_scripts = {
    'centos': {}
}

ipxe_scripts['centos']['7'] = '''#!ipxe
kernel tftp://172.20.0.1/os/centos7/boot/vmlinuz-3.10.0-1160.el7.x86_64 {arguments} user=lkp job=/lkp/scheduled/job.yaml ip=dhcp rootovl ro root=172.20.0.1:/srv/mci/os/centos7 initrd=initramfs.lkp-3.10.0-1160.el7.x86_64.img initrd=modules-3.10.0-1160.el7.x86_64.cgz initrd=lkp-x86_64.cgz initrd=job.cgz rootfs_disk=/dev/sda
initrd tftp://172.20.0.1/os/centos7/boot/modules-3.10.0-1160.el7.x86_64.cgz
initrd tftp://172.20.0.1/os/centos7/boot/initramfs.lkp-3.10.0-1160.el7.x86_64.img
initrd tftp://172.20.0.1/job/{job_id}/job.cgz
initrd tftp://172.20.0.1/initrd/lkp-x86_64.cgz
boot
'''

class BootHandler(BaseHandler):
    def initialize(self, lkp_src, mci_home, es):
        self.es = es
        self.lkp_src = lkp_src
        self.mci_home = mci_home

    def get(self):
        arch = self.get_argument('arch')
        mac = self.get_argument('mac')

        # get job id from arch queue
        result = self.es.search(index='job', body={
            'size': 1,
            'sort': { 'priority': { 'order': 'asc' } },
            'query': {
                'bool': {
                    'must': [
                        { 'match': { 'os_arch': arch } },
                        { 'match': { 'state': JobState.waiting.name}},
                    ]
                },
            },
        })

        if len(result['hits']['hits']) == 0:
            logging.info(f'no job needs to be executed: mac={mac}, arch={arch}')
            self.finish('#!ipxe\nsleep 10\nreboot')
            self.es.index(index='machines', id=mac, document={
                'mac': mac,
                'arch': arch,
                'state': MachineState.idle.name,
            })
            return

        job = result['hits']['hits'][0]['_source']

        # generate job.cgz and store it into TFTP
        jobs.create_job_package(job, self.mci_home, self.lkp_src)

        # generate ipxe script
        if job['os'] not in ipxe_scripts or job['os_version'] not in ipxe_scripts[job['os']]:
            logging.warning(f'this dist not support and use centos7 instead: os={job["os"]}, version={job["os_version"]}')
            script = ipxe_scripts['centos']['7']
        else:
            script = ipxe_scripts[job['os']][job['os_version']]

        # TODO: clean code
        arguments = ''
        plan = self.es.get(index='plan', id=job['plan'])['_source']
        for path in plan['config']['packages']:
            arguments = f'http://172.20.0.1:3080/{path},{arguments}'
        arguments=f'packages={arguments[:-1]}'
        script = script.format(job_id=job['id'], arguments=arguments)
        logging.info(f'send boot.ipxe script: job_id={job["id"]}, mac={mac}, script={script}')
        self.finish(script)

        # update job and test machine state after successful request
        job['state'] = JobState.running.name
        self.es.index(index='job', id=job['id'], document=job)
        self.es.index(index='machine', id=mac, document={
            'mac': mac,
            'arch': arch,
            'state': MachineState.busy.name,
        })

        while True:
            result = self.es.get(index='plan', id=job['plan'])
            plan = result['_source']
            stage_idx = next(idx for idx, stage in enumerate(plan['stages']) \
                             if stage['name'] == job['stage'])
            stage = plan['stages'][stage_idx]
            if stage['state'] != StageState.waiting.name:
                break

            stage['state'] = StageState.running.name
            try:
                self.es.index(index='plan', id=plan['id'], document=plan)
            except elasticsearch.ConflictError as err:
                logging.warning(f'retry to handle result since concurrency control failed: err={err}')
            else:
                logging.debug(f'result dealt successfully')
                break
