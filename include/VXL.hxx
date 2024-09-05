#pragma once

// https://github.com/piqueserver/piqueserver/blob/master/pyspades/vxl_c.cpp
#include <unordered_set>
#include <vector>
#include <mutex>
#include <queue>

#include <vxl_c.h>

#include <Milsim/Vector.hxx>

std::mutex onDeleteMutex; // do we really need this?
std::queue<int> onDeleteQueue;

void deleteQueueClear() {
    onDeleteMutex.lock();
    onDeleteQueue = {};
    onDeleteMutex.unlock();
}

int deleteQueuePop() {
    onDeleteMutex.lock();
    int retval = -1;

    if (!onDeleteQueue.empty()) {
        retval = onDeleteQueue.front();
        onDeleteQueue.pop();
    }

    onDeleteMutex.unlock();

    return retval;
}

inline void visit(std::vector<Vector3i> & out, int x, int y, int z, MapData * M) {
    if (x < 0 || x > 511 || y < 0 || y > 511 || z < 0 || z > 63)
        return;

    if (!M->geometry[get_pos(x, y, z)])
        return;

    out.emplace_back(x, y, z);
}

int traverseNode(int x, int y, int z, MapData * M, int destroy) {
    constexpr size_t nodeReserveSize = 250000;

    static std::vector<Vector3i> queue;
    static std::unordered_set<int> marked;

    if (queue.capacity() < nodeReserveSize)
        queue.reserve(nodeReserveSize);

    queue.emplace_back(x, y, z);

    while (!queue.empty()) {
        Vector3i & v = queue.back();
        int x = v.x, y = v.y, z = v.z;

        if (z >= 62) {
            queue.clear();
            marked.clear();
            return 0;
        }

        queue.pop_back();

        int i = get_pos(x, y, z);

        auto [_, inserted] = marked.insert(i);

        if (inserted) { // already visited?
            visit(queue, x, y, z - 1, M);
            visit(queue, x, y - 1, z, M);
            visit(queue, x, y + 1, z, M);
            visit(queue, x - 1, y, z, M);
            visit(queue, x + 1, y, z, M);
            visit(queue, x, y, z + 1, M);
        }
    }

    onDeleteMutex.lock();

    // destroy the node’s path!
    if (destroy) for (auto i : marked) {
        M->geometry[i] = 0;
        M->colors.erase(i);
        onDeleteQueue.push(i);
    }

    onDeleteMutex.unlock();

    int amount = marked.size();
    queue.clear();
    marked.clear();

    return amount;
}