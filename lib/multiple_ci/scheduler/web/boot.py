import logging

import tornado.web

from multiple_ci.model.job_status import JobStatus
from multiple_ci.model.machine_status import MachineStatus
from multiple_ci.utils import jobs

ipxe_scripts = {
    'centos': {}
}

ipxe_scripts['centos']['7'] = '''
#!ipxe
initrd tftp://172.20.0.1/centos7-iso/boot/modules-3.10.0-1160.el7.x86_64.cgz
initrd tftp://172.20.0.1/centos7-iso/boot/initramfs.lkp-3.10.0-1160.el7.x86_64.img
initrd tftp://172.20.0.1/jobs/{job_id}/job.cgz
initrd tftp://172.20.0.1/common/lkp-x86_64.cgz
kernel tftp://172.20.0.1/centos7-iso/boot/vmlinuz-3.10.0-1160.el7.x86_64 user=lkp job=/lkp/scheduled/job.yaml ip=dhcp rootovl ro root=172.20.0.1:/mnt/sda/centos7-iso initrd=initramfs.lkp-3.10.0-1160.el7.x86_64.img initrd=modules-3.10.0-1160.el7.x86_64.cgz initrd=lkp-x86_64.cgz initrd=job.cgz rootfs_disk=/dev/sda
boot
'''

class BootHandler(tornado.web.RequestHandler):
    def data_received(self, chunk): pass

    def initialize(self, lkp_src, job_dir, es):
        self.es = es
        self.lkp_src = lkp_src
        self.job_dir = job_dir

    def get(self):
        arch = self.get_argument('arch')
        mac = self.get_argument('mac')

        # get job id from arch queue
        result = self.es.search('jobs', body={
            'size': 1,
            'sort': { 'priority': { 'order': 'asc' } },
            'query': {
                'match': {
                    'os_arch': arch,
                    'status': JobStatus.waiting.name,
                }
            },
        })
        if len(result['hits']['hits']) == 0:
            self.write('#!ipxe\nreboot')
            self.es.index(index='machines', id=mac, document={
                'mac': mac,
                'arch': arch,
                'status': MachineStatus.idle.name,
            })
            return

        # update job and test machine status
        job = result['hits']['hits'][0]['_source']
        job['status'] = JobStatus.running.name
        self.es.index(index='jobs', id=job['id'], document=job)

        self.es.index(index='machines', id=mac, document={
            'mac': mac,
            'arch': arch,
            'status': MachineStatus.busy.name,
        })

        # generate job.cgz and store it into TFTP
        jobs.generate_id(job)
        jobs.create_job_package(job, self.job_dir, self.lkp_src)

        # generate ipxe script
        if job['os'] not in ipxe_scripts or job['os_version'] not in ipxe_scripts[job['os']]:
            logging.warning(f'this dist or version not support yet: os={job["os"]}, version={job["os_version"]}')
            self.write(ipxe_scripts['centos']['7'].format(job_id=job['id']))
        else:
            self.write(ipxe_scripts[job['os']][job['os_version']].format(job_id=job['id']))