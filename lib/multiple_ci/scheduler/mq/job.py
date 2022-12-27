import logging

def handle_submit(ch, method, properties, body):
    # TODO: create a job, store it into ES, send into arch queue (maybe etcd), and update job status
    # TODO: generate job.cgz and store it into TFTP
    logging.info(f'received job config: config={body}')