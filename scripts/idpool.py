from itertools import count, filterfalse

class IDPool:
    def __init__(self, protocol):
        self.protocol = protocol

    def pop(self):
        return next(filterfalse(self.protocol.players.__contains__, count()))

    def put_back(self, id):
        pass

def apply_script(protocol, connection, config):
    class IDPoolProtocol(protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)
            self.player_ids = IDPool(self)

    return IDPoolProtocol, connection