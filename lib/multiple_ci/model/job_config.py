class JobConfig(dict):
    def __init__(self, config):
        dict.__init__(self, **config)

    def __lt__(self, other):
        return self['name'] < other['name']