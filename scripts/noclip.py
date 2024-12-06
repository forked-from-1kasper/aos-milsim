def apply_script(protocol, connection, config):
    class NoclipConnection(connection):
        def is_stuck(self, x, y, z):
            M = self.protocol.map

            if self.world_object.crouch:
                return M.get_solid(x, y, z) or M.get_solid(x, y, z + 1)
            else:
                return M.get_solid(x, y, z) or M.get_solid(x, y, z + 1) or M.get_solid(x, y, z + 2)

        def check_speedhack(self, x2, y2, z2, distance = None):
            x1, y1, z1 = self.world_object.position.get()

            # TODO: is there any way to prevent tunnelling through walls?
            if self.is_stuck(x1, y1, z1) or self.is_stuck(x2, y2, z2):
                return False

            return connection.check_speedhack(self, x2, y2, z2, distance)

    return protocol, NoclipConnection
