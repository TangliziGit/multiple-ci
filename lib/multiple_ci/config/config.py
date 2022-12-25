REPO_QUEUE_CAPACITY = 10000
SCANNER_COUNT = 10
# UPSTREAM_REPO = "TangliziGit/multiple-ci-repos"
# UPSTREAM_URL = f"https://github.com/{UPSTREAM_REPO}"
UPSTREAM_REPO = "wu_fengguang/upstream-repos"
UPSTREAM_URL = f"https://gitee.com/{UPSTREAM_REPO}"

REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

MQ_HOST = 'localhost'

# 60 minutes to trigger timeout checker
CHECKER_TIMEOUT_NS = 60 * 60 * 10**9
CHECKER_COMMIT_COUNT_THRESHOLD = 5
