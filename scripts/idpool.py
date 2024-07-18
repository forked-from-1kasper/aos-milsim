from itertools import count

class IDPool:
    def __init__(self, protocol):
        self.protocol = protocol

    def pop(self):
        for player_id in count():
            if player_id not in self.protocol.players:
                return player_id

    def put_back(self, id):
        pass

def apply_script(protocol, connection, config):
    class IDPoolProtocol(protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)
            self.player_ids = IDPool(self)

    return IDPoolProtocol, connection