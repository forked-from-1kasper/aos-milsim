class ABCTileEntityManager:
    def __new__(Klass, *w, **kw):
        raise NotImplementedError

    def __init__(self):
        self.tile_entities = {}

    def add_tile_entity(self, klass, *w, **kw):
        entity = klass(*w, **kw)
        self.tile_entities[entity.position] = entity

        return entity

    def get_tile_entity(self, x, y, z):
        return self.tile_entities.get((x, y, z))

    def remove_tile_entity(self, x, y, z):
        self.tile_entities.pop((x, y, z))

    def clear_tile_entities(self):
        self.tile_entities.clear()
