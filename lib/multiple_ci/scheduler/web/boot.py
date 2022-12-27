import tornado.web

ipxe_script = '''
#!ipxe
initrd tftp://172.20.0.1/centos7-iso/boot/modules-3.10.0-1160.el7.x86_64.cgz
initrd tftp://172.20.0.1/centos7-iso/boot/initramfs.lkp-3.10.0-1160.el7.x86_64.img
kernel tftp://172.20.0.1/centos7-iso/boot/vmlinuz-3.10.0-1160.el7.x86_64 user=lkp job=/lkp/scheduled/job.yaml ip=dhcp rootovl ro root=172.20.0.1:/mnt/sda/centos7-iso initrd=initramfs.lkp-3.10.0-1160.el7.x86_64.img initrd=modules-3.10.0-1160.el7.x86_64.cgz rootfs_disk=/dev/sda
boot
'''

class BootHandler(tornado.web.RequestHandler):
    def data_received(self, chunk): pass

    def get(self):
        # TODO: get job id from arch queue, update job and test machine status, and generate ipxe script
        arch = self.get_argument('arch')
        mac = self.get_argument('mac')
        self.write(ipxe_script)