#pragma once

/*
    Copyright © 2024 rzrn

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/

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
