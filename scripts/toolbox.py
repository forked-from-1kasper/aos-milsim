from piqueserver.config import config
from piqueserver.commands import command

@command(admin_only=True)
def elevate(conn, *args):
    if not conn.hp: return

    x, y, _ = conn.world_object.position.get()
    z = conn.protocol.map.get_z(x, y) - 3

    conn.set_location_safe((x, y, z))

@command('position')
def position(conn, *args):
    return str(conn.world_object.position)

discord = config.section("discord")

invite = discord.option("invite", "<no invite>").get()
description = discord.option("description", "Discord").get()

@command()
def discord(conn, *args):
    return "%s: %s" % (description, invite)

def apply_script(protocol, connection, config):
    class ToolboxConnection(connection):
        def on_connect(self):
            self.chat_limiter._seconds = 0
            return connection.on_connect(self)

        def on_flag_take(self):
            flag = self.team.other.flag

            if self.world_object.position.z >= flag.z:
                return False

            if not self.world_object.can_see(flag.x, flag.y, flag.z - 0.5):
                return False

            return connection.on_flag_take(self)

    return protocol, ToolboxConnection