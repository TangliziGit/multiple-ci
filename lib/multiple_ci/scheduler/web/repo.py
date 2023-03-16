from multiple_ci.utils.handler import JsonBaseHandler
from multiple_ci.config import config

class RepoListHandler(JsonBaseHandler):
    def initialize(self, es):
        self.es = es

    def get(self):
        # Fuck ES DSL, and praise chatGPT
        plan_resp = self.es.search(index='plan', size=0, aggs={
            "group_by_name": {
                "terms": { "field": "name" },
                "aggs": {
                    "filter_success": {
                        "filter": { "term": { "state": "success" } },
                        "aggs": {
                            "avg_duration": {
                                "avg": {
                                    "script": {
                                        "lang": "painless",
                                        "source": "doc['end_time'].value - doc['start_time'].value"
                                    }
                                }
                            },
                        }
                    }
                }
            },
        })

        job_resp = self.es.search(index='job', size=0, aggs={
            "group_by_name": {
                "terms": {
                    "field": "name"
                }
            },
        })

        job_buckets = job_resp['aggregations']['group_by_name']['buckets']
        job_count_dict = {}
        for b in job_buckets:
            job_count_dict[b['key']] = b['doc_count']

        plan_buckets = plan_resp['aggregations']['group_by_name']['buckets']
        repos = []
        for bucket in plan_buckets:
            name = bucket['key']
            count = bucket['doc_count']
            success_count = bucket['filter_success']['doc_count']
            avg_duration = bucket['filter_success']['avg_duration']['value'] if success_count > 0 else 0
            repos.append({
                'name': name,
                'job_count': job_count_dict[name],
                'plan_count': count,
                'success_rate': success_count / count,
                'avg_duration': avg_duration,
            })
        self.ok(payload=repos)

class RepoHandler(JsonBaseHandler):
    def initialize(self, es):
        self.es = es

    def get(self, name):
        plan_resp = self.es.search(index='plan', size=0, aggs={
            "filter_name": {
                "filter": {"term": {"name": "sleep"}},
                "aggs": {
                    "filter_success": {
                        "filter": {"term": {"state": "success"}},
                        "aggs": {
                            "avg_duration": {
                                "avg": {
                                    "script": {
                                        "lang": "painless",
                                        "source": "doc['end_time'].value - doc['start_time'].value"
                                    }
                                }
                            },
                        }
                    }
                }
            }
        })

        job_resp = self.es.search(index='job', size=0, aggs={
            "filter_name": {
                "filter": {"term": {"name": "sleep"}},
            }
        })

        plans_by_name = plan_resp['aggregations']['filter_name']
        success_plan_count = plans_by_name['filter_success']['doc_count']
        self.ok(payload={
            'name': name,
            'job_count': job_resp['aggregations']['filter_name']['doc_count'],
            'plan_count': plans_by_name['doc_count'],
            'success_rate': plans_by_name['doc_count'] / success_plan_count,
            'avg_duration': plans_by_name['filter_success']['avg_duration']['value'] if success_plan_count > 0 else 0,
        })

class PlanListByRepoHandler(JsonBaseHandler):
    def initialize(self, es):
        self.es = es

    def get(self, name):
        res = self.es.search(index='plan',
                             size=config.API_SEARCH_SIZE,
                             query={'term': {'name': name}})['hits']['hits']

        plans = [r['_source'] for r in res]
        self.ok(payload=plans)
