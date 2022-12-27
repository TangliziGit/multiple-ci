import logging

import redis


class CacheManager:
    pool = None
    inited = False

    @classmethod
    def init(cls, host, port, db):
        if cls.inited:
            logging.warning(f'cache manager init twice')
            return
        cls.inited = True
        cls.pool = redis.ConnectionPool(host=host, port=port, db=db)

    # NOTE: do not forget to close redis client
    @classmethod
    def get_client(cls):
        if not cls.inited:
            logging.error(f'cache manager have not inited')
            return None
        return redis.Redis(connection_pool=cls.pool)
