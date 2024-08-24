from itertools import count, filterfalse

class IDPool(set):
    def __init__(self, protocol):
        self.protocol = protocol
        super().__init__()

    def pop(self):
        ID = next(filterfalse(self.__contains__, count()))
        self.add(ID)
        return ID

    def put_back(self, ID):
        self.remove(ID)

def apply_script(protocol, connection, config):
    class IDPoolProtocol(protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)
            self.player_ids = IDPool(self)

    return IDPoolProtocol, connection