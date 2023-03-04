import logging

import elasticsearch

from multiple_ci.utils import jobs
from multiple_ci.config import config
from multiple_ci.model.job_state import JobState
from multiple_ci.model.stage_state import StageState
from multiple_ci.model.machine_state import MachineState
from multiple_ci.scheduler.web.util import BaseHandler

ipxe_scripts = {
    'x86_64': {
        'centos': {
            '7': {
                'kernel': 'tftp://172.20.0.1/os/centos7/boot/vmlinuz-3.10.0-1160.el7.x86_64',
                'initramfs': 'tftp://172.20.0.1/os/centos7/boot/initramfs.lkp-3.10.0-1160.el7.x86_64.img',
                'arguments': [
                    'user=lkp',
                    'job=/lkp/scheduled/job.yaml',
                    'ip=dhcp rootovl ro',
                    'root=172.20.0.1:/srv/mci/os/centos7',
                    'selinux=0',
                    # 'rd.shell rd.debug log_buf_len=1M',
                    # 'rd.break=cleanup',
                ],
                'initrd': [
                    'tftp://172.20.0.1/initrd/lkp-x86_64.cgz'
                ],
            }
        }
    },
    'aarch64': {
        'debian': {
            '11': {
                'kernel': 'tftp://172.20.0.1/os/debian11-aarch64/boot/vmlinuz-5.10.0-21-arm64',
                'initramfs': 'tftp://172.20.0.1/os/debian11-aarch64/boot/initramfs.lkp-5.10.0-21-arm64.img',
                'arguments': [
                    'user=lkp',
                    'job=/lkp/scheduled/job.yaml',
                    'ip=dhcp rootovl ro',
                    'selinux=0',
                    'root=172.20.0.1:/srv/mci/os/debian11-aarch64',
                    # 'rd.shell rd.debug log_buf_len=1M',
                    # 'rd.break=cleanup',
                ],
                'initrd': [
                    'tftp://172.20.0.1/initrd/lkp-x86_64.cgz'
                ],
            }
        }
    },
}

def generate_ipxe_script(arch, os, os_version, kernel, initramfs, arguments, initrd):
    """
    Ipxe scripts generator. Below is an output example:
    #!ipxe
    kernel tftp://172.20.0.1/os/centos7/boot/vmlinuz-3.10.0-1160.el7.x86_64 {arguments} user=lkp job=/lkp/scheduled/job.yaml ip=dhcp rootovl ro root=172.20.0.1:/srv/mci/os/centos7 initrd=initramfs.lkp-3.10.0-1160.el7.x86_64.img initrd=modules-3.10.0-1160.el7.x86_64.cgz initrd=lkp-x86_64.cgz initrd=job.cgz
    initrd tftp://172.20.0.1/os/centos7/boot/modules-3.10.0-1160.el7.x86_64.cgz
    initrd tftp://172.20.0.1/os/centos7/boot/initramfs.lkp-3.10.0-1160.el7.x86_64.img
    initrd tftp://172.20.0.1/job/{job_id}/job.cgz
    initrd tftp://172.20.0.1/initrd/lkp-x86_64.cgz
    boot
    """
    if arch not in ipxe_scripts or \
            os not in ipxe_scripts[arch] or\
            os_version not in ipxe_scripts[arch][os]:
        logging.warning(f'this dist not support and use centos7 instead: os={os}, version={os_version}')
        os = 'centos'
        os_version = '7'

    default = ipxe_scripts[arch][os][os_version]
    if arguments is None:
        arguments = []
    if initrd is None:
        initrd = []
    if kernel is None or kernel == '':
        kernel = default['kernel']

    initrd += default['initrd']
    if initramfs is not None:
        initrd.append(initramfs)
    else:
        initrd.append(default['initramfs'])

    arguments += ipxe_scripts[arch][os][os_version]['arguments']
    for url in initrd:
        arguments.append(f'initrd={url.split("/")[-1]}')

    scripts = '#!ipxe\n'
    scripts += f'kernel {kernel} {" ".join(arguments)}\n'
    for url in initrd:
        scripts += f'initrd {url}\n'
    scripts += 'boot'
    return scripts

class BootHandler(BaseHandler):
    def initialize(self, lkp_src, mci_home, es, monitor, latch):
        self.es = es
        self.monitor = monitor
        self.lkp_src = lkp_src
        self.mci_home = mci_home
        self.latch = latch

    def get(self):
        with self.latch:
            arch = self.get_argument('arch')
            mac = self.get_argument('mac')
            self.monitor.pong(mac=mac)

            logging.info(f"testbox request job: arch={arch}, mac={mac}")
            if arch == 'arm64':
                arch = 'aarch64'

            # get job id from arch queue
            # FIXME: get job randomly to avoid data race
            result = self.es.search(index='job', body={
                'size': 1,
                'sort': { 'priority': { 'order': 'desc' } },
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
                    'job': ''
                })
                return

            job = result['hits']['hits'][0]['_source']

            # generate job.cgz and store it into TFTP
            job_created = jobs.create_job_package(job, self.mci_home, self.lkp_src)
            if not job_created:
                # assert: job.state == running | done
                logging.info(f'data race occurred, need retry: mac={mac}, arch={arch}, job_id={job["id"]}')
                self.finish(f'#!ipxe\nreboot')
                self.es.index(index='machine', id=mac, document={
                    'mac': mac,
                    'arch': arch,
                    'state': MachineState.idle.name,
                    'job': ''
                })
                return

            # generate ipxe script
            plan = self.es.get(index='plan', id=job['plan'])['_source']
            configure = plan['config']
            packages = [f'http://172.20.0.1:3080/{p}' for p in configure['packages']]

            arguments = [ f'packages={",".join(packages)}' ]
            initrd = [ f'tftp://172.20.0.1/job/{job["id"]}/job.cgz' ]

            initramfs, kernel = None, None
            initramfs_path = None
            if configure['kernel'] != '':
                kernel = f"http://172.20.0.1:3080/{configure['kernel']}"
                if configure['initramfs'] == '':
                    kernel_path = f'/srv/result/{configure["kernel"]}'
                    initramfs = jobs.generate_lkp_initramfs(kernel_path, self.lkp_src)
                    initramfs = initramfs.replace('/srv/result/', '')
                    initramfs_path = initramfs
                    configure['initramfs'] = initramfs
                initramfs = f"http://172.20.0.1:3080/{configure['initramfs']}"

            script = generate_ipxe_script(job['os_arch'], job['os'], job['os_version'], kernel, initramfs, arguments, initrd)
            logging.info(f'send boot.ipxe script: job_id={job["id"]}, mac={mac}, script={script}')
            self.finish(script)

            # update job and test machine state after successful request
            job['state'] = JobState.running.name
            job['machine'] = mac
            self.es.index(index='job', id=job['id'], document=job)
            self.es.index(index='machine', id=mac, document={
                'mac': mac,
                'arch': arch,
                'state': MachineState.busy.name,
                'job': job['id']
            })

            while True:
                result = self.es.get(index='plan', id=job['plan'])
                plan = result['_source']
                stage_idx = next(idx for idx, stage in enumerate(plan['stages']) \
                                 if stage['name'] == job['stage'])
                stage = plan['stages'][stage_idx]

                if initramfs_path is not None:
                    plan['config']['initramfs'] = initramfs_path
                stage['state'] = StageState.running.name
                try:
                    self.es.index(index='plan', id=plan['id'], document=plan)
                except elasticsearch.ConflictError as err:
                    logging.warning(f'retry to handle result since concurrency control failed: err={err}')
                else:
                    logging.debug(f'result dealt successfully')
                    break
