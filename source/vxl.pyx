from pyspades.vxl cimport VXLData, MapData

cdef extern from "VXL.hxx":
    int traverseNode(int, int, int, MapData *, int)
    int c_deleteQueuePop "deleteQueuePop"()
    void c_deleteQueueClear "deleteQueueClear"()

cdef class VxlData(VXLData):
    cpdef int check_node(self, int x, int y, int z, bint destroy = False):
        return traverseNode(x, y, z, self.map, destroy)

cdef extern from "vxl_c.h":
    void get_xyz(int, int *, int *, int *)

cdef extern from "world_c.cpp":
    MapData * global_map

    int c_can_see "can_see"(
        MapData *,
        float x0, float y0, float z0,
        float x1, float y1, float z1
    )

    int c_cast_ray "cast_ray"(
        MapData *, float x0, float y0, float z0,
        float x1, float y1, float z1, float length,
        long * x, long * y, long * z
    )

def can_see(VXLData data, float x0, float y0, float z0, float x1, float y1, float z1):
    global global_map
    global_map = data.map

    cdef bint retval = c_can_see(NULL, x0, y0, z0, x1, y1, z1)
    return retval

def cast_ray(VXLData data, float x0, float y0, float z0, float x1, float y1, float z1, float length):
    global global_map
    global_map = data.map

    cdef long x = -1, y = -1, z = -1

    if c_cast_ray(NULL, x0, y0, z0, x1, y1, z1, length, &x, &y, &z):
        return (x, y, z)
    else:
        return None

def deleteQueueClear():
    c_deleteQueueClear()

def onDeleteQueue():
    cdef int x, y, z, index

    while True:
        index = c_deleteQueuePop()

        if index < 0:
            return

        get_xyz(index, &x, &y, &z)
        yield (x, y, z)
