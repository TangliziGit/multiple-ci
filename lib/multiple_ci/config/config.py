# -------------------- critical config --------------------
SCANNER_REPO_QUEUE_CAPACITY = 10000
SCANNER_COUNT = 5
SCANNER_INTERVAL_SEC = 1

CHECKER_TIMEOUT_NS = 60 * 60 * 10**9    # 60 minutes
CHECKER_COMMIT_COUNT_THRESHOLD = 5

# -------------------- default CLI config --------------------
DEFAULT_UPSTREAM_REPO = "wu_fengguang/upstream-repos"
DEFAULT_UPSTREAM_URL = f"https://gitee.com/{DEFAULT_UPSTREAM_REPO}"

DEFAULT_REDIS_HOST = 'localhost'
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 0

DEFAULT_MQ_HOST = 'localhost'
