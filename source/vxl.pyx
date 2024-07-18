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
