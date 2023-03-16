# -------------------- critical config --------------------
SCANNER_REPO_QUEUE_CAPACITY = 10000
SCANNER_COUNT = 2
SCANNER_INTERVAL_SEC = 5

CHECKER_TIMEOUT_NS = 60 * 60 * 10**9    # 60 minutes
CHECKER_COMMIT_COUNT_THRESHOLD = 5

LKP_RESULT_ROOT = '/result'
LKP_SERVER = '172.20.0.1'

HEARTBEAT_INTERVAL_SEC = 5
X86_64_MACHINE_DOWN_TIMER_SEC = 30
AARCH64_MACHINE_DOWN_TIMER_SEC = 150
DOWNTIME_COUNT = 3

API_SEARCH_SIZE = 1000
GIT_TXN_LOCK_TIMEOUT_NS = 5 * 10 ** 9       # 5 seconds
GIT_TXN_SPINLOCK_INTERVAL_SEC = 20 / 1000   # 20 ms

EMAIL_HOST = "smtp.qq.com"
EMAIL_USERNAME = "tanglizimail"
EMAIL_PASSWORD = "qqmwqkjewqiebfgc"
EMAIL_SENDER = 'tanglizimail@foxmail.com'

# -------------------- default CLI config --------------------
DEFAULT_UPSTREAM_URL = f"https://github.com/TangliziGit/multiple-ci-repos"
DEFAULT_MULTIPLE_CI_HOME = '/srv/mci'
DEFAULT_LKP_SRC = '/srv/lkp'

DEFAULT_REDIS_HOST = 'localhost'
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 0

DEFAULT_MQ_HOST = 'localhost'
DEFAULT_ES_ENDPOINT = 'http://localhost:9200'

DEFAULT_SCHEDULER_WEB_PORT = 3000
DEFAULT_SCHEDULER_ENDPOINT = f'localhost:{DEFAULT_SCHEDULER_WEB_PORT}'
