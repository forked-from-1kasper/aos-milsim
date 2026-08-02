from collections import deque
from threading import Thread
from time import monotonic
from math import inf

from itertools import cycle

from horseradish.commands import command, get_player

from pyspades.common import encode

PACKET_EXT_BASE = 0x40

class PacketGraph:
    ext_id = 0x12
    ext_version = 1

    id = PACKET_EXT_BASE + ext_id

class PacketFigureAdd:
    ext_id = 0x12
    ext_version = 1

    id = PACKET_EXT_BASE + ext_id
    subID = 0

    def __init__(self, index, cols, plots):
        self.index = index
        self.cols  = cols
        self.plots = plots

    def write(self, writer):
        writer.writeUInt8LE(self.id)
        writer.writeUInt8LE(self.subID)
        writer.writeUInt8LE(self.index)
        writer.writeUInt8LE(self.cols)

        for (r, g, b), label in self.plots:
            writer.writeUInt8LE(b)
            writer.writeUInt8LE(g)
            writer.writeUInt8LE(r)
            writer.writeString(encode(label), 64)

class PacketFigureData:
    ext_id = 0x12
    ext_version = 1

    id = PACKET_EXT_BASE + ext_id
    subID = 1

    def __init__(self, index, vals):
        self.index = index
        self.vals  = vals

    def write(self, writer):
        writer.writeUInt8LE(self.id)
        writer.writeUInt8LE(self.subID)
        writer.writeUInt8LE(self.index)

        for val in self.vals:
            writer.writeFloat32LE(val)

class PacketFigureRemove:
    ext_id = 0x12
    ext_version = 1

    id = PACKET_EXT_BASE + ext_id
    subID = 2

    def __init__(self, index):
        self.index = index

    def write(self, writer):
        writer.writeUInt8LE(self.id)
        writer.writeUInt8LE(self.subID)
        writer.writeUInt8LE(self.index)

palette = [
    (63,  63, 255), (255, 127, 0),   (0,   255, 0),
    (255, 63, 63),  (255, 0,   255), (127, 0,   255),
    (255, 0,  127), (0,   255, 255), (127, 0,   127)
]

@command()
def watch(connection, nickname):
    player = get_player(connection.protocol, nickname)

    player.previous_position = None

    from milsimlib.engine import toMeters, CVRS
    from pyspades.common import Vertex3
    from math import hypot

    cvrs = CVRS()

    wo = player.world_object
    wo.body_mass = player.body_mass
    wo.gear_mass = player.gear_mass()
    wo.get_expended_energy()

    def metabolic_rate(W, L, η, V, G, walking):
        M = W + L
        n = L / W

        Mw = 1.05 * W + 2 * M * n * n + η * M * (1.5 * V * V + 0.35 * V * G)

        # Mw = 1.05 * W + 2 * M * n * n + η * M * (1.5 * V * V + 0.35 * V * G)
        #    = 1.05 * W + 2 * M * n * n + 1.5 * η * M * V * V + 0.35 * η * M * V * G

        if walking:
            return Mw
        else:
            Mr = Mw - 0.5 * (1 - 0.01 * L) * (Mw - 15 * L - 850)
            return Mr

    def funval():
        if wo := player.world_object:
            if player.previous_position is None:
                player.previous_position = wo.position.copy()

                return [-inf, -inf, -inf, -inf], [-inf, -inf, -inf, -inf], [-inf, -inf, -inf]
            else:
                R1, R2 = player.previous_position, wo.position

                Δx, Δy, Δz = (R2 - R1).get()

                d = hypot(Δx, Δy)
                G = 0 if d < 1e-5 else abs(Δz) / d
                if Δz > 0: G = 0.15 * G

                vx, vy, vz = wo.velocity.get()
                V = 2.88 * hypot(vx, vy)

                #M = metabolic_rate(player.body_mass, player.gear_mass(), 1.2, V, G, not wo.sprint)

                wo.body_mass = player.body_mass
                wo.gear_mass = player.gear_mass()
                M = wo.get_expended_energy() / 1.0

                #print("M = {:.2f} W".format(M))

                player.previous_position = wo.position.copy()
                MRO2 = 0.0028 * M

                cvrs.tick(1.0)
                cvrs.MRO2 = MRO2

                DO2 = cvrs.Ql * cvrs.CaO2
                VO2 = cvrs.Qs * (cvrs.CaO2 - cvrs.CvO2)

                return [cvrs.HR / 200, cvrs.Pas / 200, cvrs.Pap / 100, MRO2], [cvrs.PaCO2 / 100, cvrs.PaO2 / 200, cvrs.PvCO2 / 100, cvrs.PvO2 / 100], [cvrs.VA / 50, DO2 / 5, VO2 / 5]
        else:
            return [-inf, -inf, -inf, -inf], [-inf, -inf, -inf, -inf], [-inf, -inf, -inf]

    player.funval = funval

    player.send_contained(PacketFigureAdd(4, 10, [((255, 0, 0), "TEST")]), sequence = True)
    player.send_contained(PacketFigureRemove(4), sequence = True)

    player.send_contained(PacketFigureAdd(
        0, 10, [((0, 0, 0), "test 1"), ((255, 255, 255), "test 2")]
    ), sequence = True)

    plot1 = "Heart Rate (BPM / 200)"
    plot2 = "Pas (mmHg / 200)"
    plot3 = "Pap (mmHg / 100)"
    plot4 = "MRO₂ (L / min)"

    fig1 = list(zip(cycle(palette), [plot1, plot2, plot3, plot4]))
    player.send_contained(PacketFigureAdd(0, 50, fig1), sequence = True)

    plot1 = "PaCO₂ (mmHg / 100)"
    plot2 = "PaO₂ (mmHg / 200)"
    plot3 = "PvCO₂ (mmHg / 100)"
    plot4 = "PvO₂ (mmgHg / 100)"

    fig2 = list(zip(cycle(palette), [plot1, plot2, plot3, plot4]))
    player.send_contained(PacketFigureAdd(1, 50, fig2), sequence = True)

    plot1 = "VA (L / min / 50)"
    plot2 = "DO₂ (L / min / 5)" # L / min or L?
    plot3 = "VO₂ (L / min / 5)"

    fig3 = list(zip(cycle(palette), [plot1, plot2, plot3]))
    player.send_contained(PacketFigureAdd(2, 50, fig3), sequence = True)

def apply_script(protocol, connection, config):
    class DataplotConnection(connection):
        funval = None

    class DataplotProtocol(protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)

            self.dataplot_timer = 0

        def on_world_update(self):
            t = monotonic()

            if t - self.dataplot_timer > 1:
                self.dataplot_timer = t

                for player in self.living():
                    if funval := player.funval:
                        vals1, vals2, vals3 = funval()

                        player.send_contained(PacketFigureData(0, vals1), sequence = True)
                        player.send_contained(PacketFigureData(1, vals2), sequence = True)
                        player.send_contained(PacketFigureData(2, vals3), sequence = True)

            protocol.on_world_update(self)

    return DataplotProtocol, DataplotConnection