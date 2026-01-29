/*
    Copyright © 2011–2012 Mathias Kaerlev
    Copyright © 2024 rzrn

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/

#include <VXL.hxx>

// https://github.com/piqueserver/piqueserver/blob/master/pyspades/vxl_c.cpp
#include <unordered_set>

#include <mutex>
#include <queue>

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
