def apply_script(protocol, connection, config):
    class NoclipProtocol(protocol):
        def is_solid(self, x, y, z):
            return 0 <= z < 63 and self.map.get_solid(x, y, z)

    class NoclipConnection(connection):
        def is_stuck(self, x, y, z):
            protocol = self.protocol

            if self.world_object.crouch:
                return protocol.is_solid(x, y, z) or protocol.is_solid(x, y, z + 1)
            else:
                return protocol.is_solid(x, y, z) or protocol.is_solid(x, y, z + 1) or protocol.is_solid(x, y, z + 2)

        def check_speedhack(self, x2, y2, z2, distance = None):
            x1, y1, z1 = self.world_object.position.get()

            # TODO: is there any way to prevent tunnelling through walls?
            if self.is_stuck(x1, y1, z1) or self.is_stuck(x2, y2, z2):
                return False

            return connection.check_speedhack(self, x2, y2, z2, distance)

    return NoclipProtocol, NoclipConnection
