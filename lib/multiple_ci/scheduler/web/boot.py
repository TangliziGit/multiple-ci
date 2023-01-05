import logging

from multiple_ci.model.job_status import JobStatus
from multiple_ci.model.machine_status import MachineStatus
from multiple_ci.utils import jobs
from multiple_ci.scheduler.web.util import BaseHandler

ipxe_scripts = {
    'centos': {}
}

ipxe_scripts['centos']['7'] = '''#!ipxe
kernel tftp://172.20.0.1/os/centos7/boot/vmlinuz-3.10.0-1160.el7.x86_64 user=lkp job=/lkp/scheduled/job.yaml ip=dhcp rootovl ro root=172.20.0.1:/srv/mci/os/centos7 initrd=initramfs.lkp-3.10.0-1160.el7.x86_64.img initrd=modules-3.10.0-1160.el7.x86_64.cgz initrd=lkp-x86_64.cgz initrd=job.cgz rootfs_disk=/dev/sda
initrd tftp://172.20.0.1/os/centos7/boot/modules-3.10.0-1160.el7.x86_64.cgz
initrd tftp://172.20.0.1/os/centos7/boot/initramfs.lkp-3.10.0-1160.el7.x86_64.img
initrd tftp://172.20.0.1/job/{job_id}/job.cgz
initrd tftp://172.20.0.1/initrd/lkp-x86_64.cgz
boot
'''

class BootHandler(BaseHandler):
    def data_received(self, chunk): pass

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
                        { 'match': { 'status': JobStatus.waiting.name } },
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
                'status': MachineStatus.idle.name,
            })
            return

        job = result['hits']['hits'][0]['_source']

        # generate job.cgz and store it into TFTP
        jobs.create_job_package(job, self.mci_home, self.lkp_src)

        # generate ipxe script
        if job['os'] not in ipxe_scripts or job['os_version'] not in ipxe_scripts[job['os']]:
            script = ipxe_scripts['centos']['7'].format(job_id=job['id'])
            logging.warning(f'this dist not support and use centos7 instead: os={job["os"]}, version={job["os_version"]}')
        else:
            script = ipxe_scripts[job['os']][job['os_version']].format(job_id=job['id'])
        logging.info(f'send boot.ipxe script: job_id={job["id"]}, mac={mac}, script={script}')
        self.finish(script)

        # update job and test machine status after successful request
        job['status'] = JobStatus.running.name
        self.es.index(index='job', id=job['id'], document=job)
        self.es.index(index='machine', id=mac, document={
            'mac': mac,
            'arch': arch,
            'status': MachineStatus.busy.name,
        })
