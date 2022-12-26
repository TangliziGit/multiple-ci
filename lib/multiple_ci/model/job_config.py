class JobConfig(dict):
    def __init__(self, config):
        dict.__init__(self, **config)

    # calculate priority in the scanning queue
    def __lt__(self, other):
        return self['time'] < other['time']