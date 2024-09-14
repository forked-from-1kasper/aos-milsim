from itertools import chain, islice, repeat
from time import monotonic
from random import randint
from zlib import crc32
import os

from twisted.logger import Logger

from piqueserver.map import MapNotFound
from piqueserver.config import config

from milsim.types import Environment

log = Logger()

def seed():
    return randint(0, 2 << 30)

def unpack(nvals, it, default = None):
    return islice(chain(it, repeat(default)), nvals)

class RotationInfo:
    def __init__(self, name):
        self.full_name = name

        name, seed = unpack(2, name.split(sep = "#", maxsplit = 1))

        self.name = name.strip()

        if seed is None:
            pass
        elif seed.isnumeric():
            self.seed = int(seed)
        else:
            self.seed = crc32(seed.encode('utf-8'))

    def get_filename(self, dirname):
        return "{}.py".format(self.name)

    def get_filepath(self, dirname):
        return os.path.join(dirname, self.get_filename(dirname))

class MapInfo:
    name = "(unnamed)"

    def __init__(self, rot_info, dirname):
        filepath = rot_info.get_filepath(dirname)

        self.attributes = dict(
            __file__            = filepath,
            __name__            = "__main__",
            author              = '(unknown)',
            version             = '1.0',
            description         = '',
            extensions          = dict(),
            time_limit          = None,
            cap_limit           = None,
            get_spawn_location  = None,
            get_entity_location = None,
            on_map_change       = None,
            on_map_leave        = None,
            on_flag_capture     = None,
            on_block_destroy    = None,
            is_indestructable   = None
        )

        try:
            fin = open(filepath, 'r')
        except OSError:
            raise MapNotFound(filepath)

        try:
            exec(
                compile(fin.read(), rot_info.get_filename(dirname), 'exec'),
                self.attributes
            )
        finally:
            fin.close()

        self.info      = self # for the backward compatibility reasons
        self.load_dir  = dirname
        self.load_path = filepath
        self.rot_info  = rot_info

        self.seed       = getattr(self.rot_info, 'seed', seed())
        self.name       = self.attributes.get('name', rot_info.name)
        self.short_name = self.name

        log.info("Loading map “{map_name}”...", map_name = self.name)

        t1 = monotonic()

        self.data = self.on_map_generation(dirname, self.seed)
        self.environment = self.on_environment_generation(dirname, self.seed)

        t2 = monotonic()

        log.info('Map loading took {duration:.2f} s', duration = t2 - t1)

        if not isinstance(self.environment, Environment):
            raise TypeError(
                "“on_environment_generation” result expected to be of the type milsim.types.Environment"
            )

    def __getattr__(self, attr):
        if attr in self.attributes:
            return self.attributes[attr]

        raise AttributeError(
            "name “{}” is not defined in the map “{}”".format(attr, self.name)
        )

def check_map(map_name, dirname):
    rot_info = RotationInfo(map_name)

    if os.path.isfile(rot_info.get_filepath(dirname)):
        return rot_info

def check_rotation(it, dirname):
    retval = list(map(RotationInfo, it))

    for rot_info in retval:
        if not os.path.isfile(rot_info.get_filepath(dirname)):
            raise MapNotFound(rot_info.name)

    return retval
