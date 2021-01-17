from piqueserver.commands import command
from piqueserver.core_commands.movement import do_move

@command(admin_only=True)
def elevate(conn, *args):
    if not conn.hp: return

    x, y, _ = conn.world_object.position.get()
    z = conn.protocol.map.get_z(x, y)

    do_move(conn, (x, y, z), silent=True)

def apply_script(protocol, connection, config):
    return protocol, connection