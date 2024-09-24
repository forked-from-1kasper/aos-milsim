#pragma once

#include <vector>

#include <vxl_c.h>

#include <Milsim/Vector.hxx>

int traverseNode(int x, int y, int z, MapData *, int destroy);

void deleteQueueClear();
int deleteQueuePop();

inline void visit(std::vector<Vector3i> & out, int x, int y, int z, MapData * M) {
    if (x < 0 || 512 <= x || y < 0 || 512 <= y || z < 0 || 64 <= z)
        return;

    if (!M->geometry[get_pos(x, y, z)])
        return;

    out.emplace_back(x, y, z);
}
