import zlib
import enet

from piqueserver.commands import command, player_only

from pyspades.packet import register_packet, register_packet_handler, _client_loaders
from pyspades import contained as loaders
from pyspades.loaders import Loader
from pyspades.common import encode

class WorldUpdate:
    id = 2

    def __init__(self, protocol, incomplete = False):
        self.protocol   = protocol
        self.incomplete = incomplete

    def write(self, writer):
        writer.writeByte(self.id, True)

        for player in self.protocol.players.values():
            x = y = z = ox = oy = oz = 0

            if self.incomplete and (not player.queued or player.team.spectator or player.world_object.dead):
                continue

            try:
                if not player.filter_visibility_data:
                    player.queued = False

                    o = player.world_object
                    x, y, z = o.position.get()
                    ox, oy, oz = o.orientation.get()
            except (KeyError, TypeError, AttributeError):
                pass

            writer.writeByte(player.player_id, True)
            writer.writeFloat(x, False)
            writer.writeFloat(y, False)
            writer.writeFloat(z, False)
            writer.writeFloat(ox, False)
            writer.writeFloat(oy, False)
            writer.writeFloat(oz, False)

@command()
@player_only
def sync(conn):
    """
    Enforce to send the complete WorldUpdate packet.
    /sync
    """
    conn.send_contained(WorldUpdate(conn.protocol))
    return "OK"

class MapStart:
    id = 18

    def __init__(self, protocol):
        self.protocol = protocol

    def write(self, writer):
        writer.writeByte(self.id, True)
        writer.writeInt(self.protocol.map_size, True, False)
        writer.writeInt(self.protocol.map_crc32, True, False)
        writer.writeString(encode(self.protocol.map_info.short_name))

# `HandShakeInit` is wrongly registered as client-side packet.
del _client_loaders[loaders.HandShakeInit.id]

@register_packet(server = False)
class MapCached(Loader):
    id = 31

    def read(self, reader):
        self.cached = reader.readByte(True)

def apply_script(protocol, connection, config):
    class Protocol076(protocol):
        version = 4

        def __init__(self, *w, **kw):
            self.world_update = WorldUpdate(self, True)
            return protocol.__init__(self, *w, **kw)

        def on_map_change(self, M):
            retval = protocol.on_map_change(self, M)

            G = M.get_generator()

            size, crc, data = 0, 0, G.get_data()

            while data is not None:
                crc = zlib.crc32(data, crc)
                size += len(data)

                data = G.get_data()

            self.map_crc32 = crc
            self.map_size  = size

            return retval

        def update_network(self):
            if len(self.players) <= 0:
                return

            self.broadcast_contained(self.world_update, unsequenced = True)

    class Connection076(connection):
        @register_packet_handler(MapCached)
        def on_map_cached_received(self, contained):
            self.map_cached = contained.cached > 0

        def __init__(self, *w, **kw):
            self.queued = False
            self.map_cached = False

            return connection.__init__(self, *w, **kw)

        def send_map(self, data = None):
            if data is not None:
                self.map_data = data
                self.send_contained(MapStart(self.protocol))
            elif self.map_data is None:
                return

            if not self.map_data.data_left() or self.map_cached:
                self.map_data = None

                for data in self.saved_loaders:
                    packet = enet.Packet(bytes(data), enet.PACKET_FLAG_RELIABLE)
                    self.peer.send(0, packet)

                self.saved_loaders = None

                self.send_contained(WorldUpdate(self.protocol))
                self.on_join()
                return

            for _ in range(10):
                if not self.map_data.data_left():
                    break
                map_data = loaders.MapChunk()
                map_data.data = self.map_data.read(8192)
                self.send_contained(map_data)

        def set_location(self, location = None):
            self.queued = True
            return connection.set_location(self, location)

        def on_position_update(self):
            self.queued = True
            return connection.on_position_update(self)

        def on_spawn(self, pos):
            self.queued = True
            return connection.on_spawn(self, pos)

        def on_orientation_update(self, x, y, z):
            retval = connection.on_orientation_update(self, x, y, z)

            if retval == False:
                return False

            self.queued = True
            return retval

    return Protocol076, Connection076