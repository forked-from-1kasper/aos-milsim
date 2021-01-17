from piqueserver.commands import command

@command(admin_only=True)
def elevate(conn, *args):
    if not conn.hp: return

    x, y, _ = conn.world_object.position.get()
    z = conn.protocol.map.get_z(x, y)

    conn.world_object.set_position(x, y, z)
    conn.on_position_update()

def apply_script(protocol, connection, config):
    return protocol, connection