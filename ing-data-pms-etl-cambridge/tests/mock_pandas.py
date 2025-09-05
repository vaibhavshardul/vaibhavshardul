class DataFrame:
    def __init__(self, *args, **kwargs):
        self.empty = kwargs.get('empty', False)
    def __len__(self):
        return 0
    def drop(self, *args, **kwargs):
        return self
    def merge(self, *args, **kwargs):
        return self
    def apply(self, *args, **kwargs):
        return self
    def astype(self, *args, **kwargs):
        return self
    def __getitem__(self, key):
        return self
    def __setitem__(self, key, value):
        pass
    def to_dict(self, *args, **kwargs):
        return {}

class Series:
    pass

def merge(df1, df2, *args, **kwargs):
    return DataFrame()

def read_csv(*args, **kwargs):
    return DataFrame()

def concat(*args, **kwargs):
    return DataFrame()
def to_datetime(*args, **kwargs):