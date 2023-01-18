import logging

import elasticsearch

from multiple_ci.utils import jobs
from multiple_ci.config import config
from multiple_ci.model.job_state import JobState
from multiple_ci.model.stage_state import StageState
from multiple_ci.model.machine_state import MachineState
from multiple_ci.scheduler.web.util import BaseHandler

ipxe_scripts = {
    'centos': {
        '7': {
            'kernel': 'tftp://172.20.0.1/os/centos7/boot/vmlinuz-3.10.0-1160.el7.x86_64',
            'arguments': [
                'user=lkp',
                'job=/lkp/scheduled/job.yaml',
                'ip=dhcp rootovl ro',
                'root=172.20.0.1:/srv/mci/os/centos7',
            ],
            'initrd': [
                'tftp://172.20.0.1/os/centos7/boot/modules-3.10.0-1160.el7.x86_64.cgz',
                'tftp://172.20.0.1/os/centos7/boot/initramfs.lkp-3.10.0-1160.el7.x86_64.img',
                'tftp://172.20.0.1/initrd/lkp-x86_64.cgz'
            ],
        }
    }
}

def generate_ipxe_script(os, os_version, kernel, arguments, initrd):
    """
    ipxe scripts generator, an output example is below:
    #!ipxe
    kernel tftp://172.20.0.1/os/centos7/boot/vmlinuz-3.10.0-1160.el7.x86_64 {arguments} user=lkp job=/lkp/scheduled/job.yaml ip=dhcp rootovl ro root=172.20.0.1:/srv/mci/os/centos7 initrd=initramfs.lkp-3.10.0-1160.el7.x86_64.img initrd=modules-3.10.0-1160.el7.x86_64.cgz initrd=lkp-x86_64.cgz initrd=job.cgz
    initrd tftp://172.20.0.1/os/centos7/boot/modules-3.10.0-1160.el7.x86_64.cgz
    initrd tftp://172.20.0.1/os/centos7/boot/initramfs.lkp-3.10.0-1160.el7.x86_64.img
    initrd tftp://172.20.0.1/job/{job_id}/job.cgz
    initrd tftp://172.20.0.1/initrd/lkp-x86_64.cgz
    boot
    """
    if os not in ipxe_scripts or os_version not in ipxe_scripts[os]:
        logging.warning(f'this dist not support and use centos7 instead: os={os}, version={os_version}')
        os = 'centos'
        os_version = '7'

    if arguments is None:
        arguments = []
    if initrd is None:
        initrd = []
    if kernel is None or kernel == '':
        kernel = ipxe_scripts[os][os_version]['kernel']

    initrd += ipxe_scripts[os][os_version]['initrd']
    arguments += ipxe_scripts[os][os_version]['arguments']
    for url in initrd:
        arguments.append(f'initrd={url.split("/")[-1]}')

    scripts = '#!ipxe\n'
    scripts += f'kernel {kernel} {" ".join(arguments)}\n'
    for url in initrd:
        scripts += f'initrd {url}\n'
    scripts += 'boot'
    return scripts

class BootHandler(BaseHandler):
    def initialize(self, lkp_src, mci_home, es, monitor):
        self.es = es
        self.monitor = monitor
        self.lkp_src = lkp_src
        self.mci_home = mci_home

    def get(self):
        arch = self.get_argument('arch')
        mac = self.get_argument('mac')
        self.monitor.pong(mac=mac)

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
            self.finish(f'#!ipxe\nsleep {config.HEARTBEAT_INTERVAL_SEC}\nreboot')
            self.es.index(index='machine', id=mac, document={
                'mac': mac,
                'arch': arch,
                'state': MachineState.idle.name,
            })
            return

        job = result['hits']['hits'][0]['_source']

        # generate job.cgz and store it into TFTP
        jobs.create_job_package(job, self.mci_home, self.lkp_src)

        # generate ipxe script
        plan = self.es.get(index='plan', id=job['plan'])['_source']
        packages = [f'http://172.20.0.1:3080/{p}' for p in plan['config']['packages']]

        arguments = [ f'packages={",".join(packages)}' ]
        initrd = [ f'ftp://172.20.0.1/job/{job["id"]}/job.cgz' ]
        kernel = plan['config']['kernel']
        script = generate_ipxe_script(job['os'], job['os_version'], kernel, arguments, initrd)

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
