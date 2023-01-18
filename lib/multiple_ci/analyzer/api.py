import http

import requests

class Apis:
    def __init__(self, scheduler_endpoint):
        self.scheduler_endpoint = scheduler_endpoint

    def cancel_stage(self, plan_id, stage_name):
        resp = requests.put(f'http://{self.scheduler_endpoint}/plan/{plan_id}/stage/{stage_name}/actions/cancel')
        return resp.status_code == http.HTTPStatus.OK
