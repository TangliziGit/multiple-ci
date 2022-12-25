import redis

from multiple_ci.config import config

pool = redis.ConnectionPool(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB)

def get_client():
    return redis.Redis(connection_pool=pool)