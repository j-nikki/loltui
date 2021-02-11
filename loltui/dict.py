from threading import Lock


class Dict(dict):
    def __init__(self):
        super().__init__()
        self.__lk = Lock()
    def write(self, k, v, overwrite=True) -> bool:
        with self.__lk:
            if overwrite or k not in self:
                self[k] = v
                return True
            return False
