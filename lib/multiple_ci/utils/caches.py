import redis


class CacheManager:
    pool = None
    inited = False

    @classmethod
    def init(cls, host, port, db):
        if cls.inited:
            # TODO: log warn
            return
        cls.inited = True
        cls.pool = redis.ConnectionPool(host=host, port=port, db=db)

    # NOTE: do not forget to close redis client
    @classmethod
    def get_client(cls):
        if not cls.inited:
            # TODO: exception
            return None
        return redis.Redis(connection_pool=cls.pool)
