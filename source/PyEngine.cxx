#include <Milsim/PyEngine.hxx>
#include <Milsim/Engine.hxx>

struct PyEngine {
    PyObject_HEAD
    Engine * ref;
};

static_assert(std::is_standard_layout_v<PyEngine> == true);

static PyObject * PyEngineNew(PyTypeObject * type, PyObject * w, PyObject * kw) {
    return type->tp_alloc(type, 0);
}

static int PyEngineInit(PyEngine * self, PyObject * w, PyObject * kw) {
    PyObject * o; if (!PyArg_ParseTuple(w, "O", &o)) return -1;

    self->ref = new Engine(o);

    self->ref->onPlayerHit = PyOwnedRef(o, "onPlayerHit");
    self->ref->onBlockHit  = PyOwnedRef(o, "onBlockHit");
    self->ref->onDestroy   = PyOwnedRef(o, "onDestroy");

    return 0;
}

static int PyEngineClear(PyEngine * self) {
    self->ref->clear();

    self->ref->protocol.retain(nullptr);
    self->ref->onTrace.retain(nullptr);
    self->ref->onBlockHit.retain(nullptr);
    self->ref->onPlayerHit.retain(nullptr);
    self->ref->onDestroy.retain(nullptr);

    return 0;
}

static void PyEngineDealloc(PyEngine * self) {
    PyObject_GC_UnTrack(self);
    PyEngineClear(self);
    Py_TYPE(self)->tp_free(self);
}

static int PyEngineTraverse(PyEngine * self, visitproc visit, void * arg) {
    Py_VISIT(self->ref->protocol);

    for (auto & o : self->ref->objects)
        Py_VISIT(o.object());

    if (self->ref->onTrace != nullptr)
        Py_VISIT(self->ref->onTrace);

    if (self->ref->onBlockHit != nullptr)
        Py_VISIT(self->ref->onBlockHit);

    if (self->ref->onPlayerHit != nullptr)
        Py_VISIT(self->ref->onPlayerHit);

    if (self->ref->onDestroy != nullptr)
        Py_VISIT(self->ref->onDestroy);

    return 0;
}

static PyObject * PyEngineLag(PyEngine * self, void *)
{ return PyEncode<double>(self->ref->lag()); }

static PyObject * PyEnginePeak(PyEngine * self, void *)
{ return PyEncode<double>(self->ref->peak()); }

static PyObject * PyEngineAlive(PyEngine * self, void *)
{ return PyEncode<size_t>(self->ref->alive()); }

static PyObject * PyEngineTotal(PyEngine * self, void *)
{ return PyEncode<size_t>(self->ref->total()); }

static PyObject * PyEngineUsage(PyEngine * self, void *)
{ return PyEncode<size_t>(self->ref->usage()); }

static PyObject * PyEngineTemperature(PyEngine * self, void *)
{ return PyEncode<double>(self->ref->temperature); }

static PyObject * PyEnginePressure(PyEngine * self, void *)
{ return PyEncode<double>(self->ref->pressure); }

static PyObject * PyEngineHumidity(PyEngine * self, void *)
{ return PyEncode<double>(self->ref->humidity); }

static PyObject * PyEngineWind(PyEngine * self, void *) {
    auto retval = PyTuple_New(3);

    auto & w = self->ref->wind;

    PyTuple_SET_ITEM(retval, 0, PyEncode<double>(w.x));
    PyTuple_SET_ITEM(retval, 1, PyEncode<double>(w.y));
    PyTuple_SET_ITEM(retval, 2, PyEncode<double>(w.z));

    return retval;
}

static PyObject * PyEngineDensity(PyEngine * self, void *)
{ return PyEncode<double>(self->ref->density()); }

static PyObject * PyEngineMach(PyEngine * self, void *)
{ return PyEncode<double>(self->ref->mach()); }

static PyObject * PyEnginePPO2(PyEngine * self, void *)
{ return PyEncode<double>(self->ref->ppo2()); }

static PyObject * PyEngineUpdate(PyEngine * self, PyObject * E) {
    self->ref->temperature = PyGetAttr<double>(E, "temperature");
    self->ref->pressure    = PyGetAttr<double>(E, "pressure");
    self->ref->humidity    = PyGetAttr<double>(E, "humidity");

    PyOwnedRef w(E, "wind");

    self->ref->wind = Vector3d(
        PyGetAttr<double>(w, "x"),
        PyGetAttr<double>(w, "y"),
        PyGetAttr<double>(w, "z")
    );

    self->ref->update();

    return Py_None;
}

static PyObject * PyEngineAdd(PyEngine * self, PyObject * w) {
    int player_id; PyObject * ro, * vo; double timestamp; PyObject * po;

    if (!PyArg_ParseTuple(w, "iOOdO", &player_id, &ro, &vo, &timestamp, &po))
        return nullptr;

    Vector3d r(
        PyGetAttr<double>(ro, "x"),
        PyGetAttr<double>(ro, "y"),
        PyGetAttr<double>(ro, "z")
    );

    Vector3d v(
        PyGetAttr<double>(vo, "x"),
        PyGetAttr<double>(vo, "y"),
        PyGetAttr<double>(vo, "z")
    );

    auto & o = self->ref->objects.emplace_back(player_id, r, v, timestamp, po);
    self->ref->trace(o.index(), o.position, 1.0, true);

    return Py_None;
}

static PyObject * PyEngineStep(PyEngine * self, PyObject * w) {
    double t1, t2;

    if (!PyArg_ParseTuple(w, "dd", &t1, &t2))
        return nullptr;

    self->ref->step(t1, t2);

    return Py_None;
}

static PyObject * PyEngineGetitem(PyEngine * self, PyObject * k) {
    int x, y, z;

    if (!PyArg_ParseTuple(k, "iii", &x, &y, &z))
        return nullptr;

    auto & voxel = self->ref->vxlData.get(x, y, z);

    auto retval = PyTuple_New(2);
    PyTuple_SET_ITEM(retval, 0, voxel.object.incref());
    PyTuple_SET_ITEM(retval, 1, PyFloat_FromDouble(voxel.durability));

    return retval;
}

static int PyEngineSetitem(PyEngine * self, PyObject * k, PyObject * o) {
    int x, y, z;

    if (!PyArg_ParseTuple(k, "iii", &x, &y, &z))
        return -1;

    if (o == nullptr) { self->ref->vxlData.erase(x, y, z); return 0; }

    if (!PyObject_TypeCheck(o, &MaterialType)) {
        PyErr_SetString(PyExc_TypeError, "must be Material");
        return -1;
    }

    self->ref->vxlData.set(x, y, z, o); return 0;
}

static PyObject * PyEngineClearMeth(PyEngine * self, PyObject *) {
    self->ref->clear();

    return Py_None;
}

static PyObject * PyEngineFlush(PyEngine * self, PyObject *) {
    self->ref->objects.clear();

    return Py_None;
}

static PyObject * PyEngineDig(PyEngine * self, PyObject * w) {
    int player_id, x, y, z; double value;

    if (!PyArg_ParseTuple(w, "iiiid", &player_id, &x, &y, &z, &value))
        return nullptr;

    if (self->ref->indestructible(x, y, z)) return Py_None;

    auto & voxel = self->ref->vxlData.get(x, y, z); auto M = voxel.material();

    if (voxel.isub(value / M->durability))
        self->ref->onDestroy(player_id, x, y, z);

    return Py_None;
}

static PyObject * PyEngineSmash(PyEngine * self, PyObject * w) {
    int player_id, x, y, z; double ΔE;

    if (!PyArg_ParseTuple(w, "iiiid", &player_id, &x, &y, &z, &ΔE))
        return nullptr;

    if (self->ref->indestructible(x, y, z)) return Py_None;

    auto & voxel = self->ref->vxlData.get(x, y, z); auto M = voxel.material();

    if (M->crumbly && randbool<double>(0.5) && self->ref->unstable(x, y, z)) {
        self->ref->onDestroy(player_id, x, y, z);
        return Py_None;
    }

    if (voxel.isub(ΔE * (M->durability / M->absorption)))
        self->ref->onDestroy(player_id, x, y, z);

    return Py_None;
}

static PyObject * PyEngineApply(PyEngine * self, PyObject * dict) {
    if (!PyDict_Check(dict)) {
        PyErr_SetString(PyExc_TypeError, "must be dict");

        return nullptr;
    }

    for (auto & [k, v] : self->ref->map()->colors) {
        PyOwnedRef i(PyEncode<unsigned int>(v & 0xFFFFFF));
        self->ref->vxlData.set(k, PyDict_GetItem(dict, i));
    }

    return Py_None;
}

static PyObject * PyEngineOnSpawn(PyEngine * self, PyObject * w) {
    int i;

    if (!PyArg_ParseTuple(w, "i", &i))
        return nullptr;

    PyOwnedRef ds(self->ref->protocol, "players");
    if (ds == nullptr) return nullptr;

    self->ref->players.resize(dictLargestKey<int>(ds) + 1);

    auto o = PyDict_GetItem(ds, PyOwnedRef(PyEncode<size_t>(i)));
    if (o == nullptr) return nullptr;

    PyOwnedRef wo(o, "world_object");
    if (wo == nullptr) return nullptr;

    PyOwnedRef p(wo, "position"), f(wo, "orientation"), c(wo, "crouch");

    auto & player = self->ref->players[i];
    player.set_crouch(c == Py_True);
    if (p != nullptr) player.set_position(vectorRef(p));
    if (f != nullptr) player.set_orientation(vectorRef(f));

    return Py_None;
}

static PyObject * PyEngineOnDespawn(PyEngine * self, PyObject * w) {
    int i;

    if (!PyArg_ParseTuple(w, "i", &i))
        return nullptr;

    auto & player = self->ref->players[i];
    player.set_crouch(false);
    player.set_position(nullptr);
    player.set_orientation(nullptr);

    PyOwnedRef ds(self->ref->protocol, "players");
    if (ds == nullptr) return nullptr;

    self->ref->players.resize(dictLargestKey<int>(ds) + 1);

    return Py_None;
}

static PyObject * PyEngineSetAnimation(PyEngine * self, PyObject * w) {
    int i, crouch;

    if (!PyArg_ParseTuple(w, "ip", &i, &crouch))
        return nullptr;

    self->ref->players[i].set_crouch(crouch);

    return Py_None;
}

static PyObject * PyEngineGetOnTrace(PyEngine * self, void *) {
    auto newref = self->ref->onTrace.incref();
    return newref == nullptr ? Py_None : newref;
}

static int PyEngineSetOnTrace(PyEngine * self, PyObject * o, void *) {
    self->ref->onTrace.retain(PyCallable_Check(o) ? o : nullptr);

    return 0;
}

static PyObject * PyEngineGetDefault(PyEngine * self, void *) {
    return self->ref->vxlData.defaultMaterial.incref();
}

static int PyEngineSetDefault(PyEngine * self, PyObject * o, void *) {
    if (!PyObject_TypeCheck(o, &MaterialType)) {
        PyErr_SetString(PyExc_TypeError, "must be Material");
        return -1;
    }

    self->ref->vxlData.defaultMaterial.retain(o);
    return 0;
}

static PyObject * PyEngineGetWater(PyEngine * self, void *) {
    return self->ref->vxlData.waterMaterial().incref();
}

static int PyEngineSetWater(PyEngine * self, PyObject * o, void *) {
    if (!PyObject_TypeCheck(o, &MaterialType)) {
        PyErr_SetString(PyExc_TypeError, "must be Material");
        return -1;
    }

    self->ref->vxlData.waterMaterial().retain(o);
    return 0;
}

static PyMappingMethods PyEngineMapping = {
    .mp_length        = NULL,
    .mp_subscript     = binaryfunc(PyEngineGetitem),
    .mp_ass_subscript = objobjargproc(PyEngineSetitem)
};

static PyMethodDef PyEngineMethods[] = {
    {"step",          PyCFunction(PyEngineStep),         METH_VARARGS, NULL},
    {"add",           PyCFunction(PyEngineAdd),          METH_VARARGS, NULL},
    {"update",        PyCFunction(PyEngineUpdate),       METH_O,       NULL},
    {"dig",           PyCFunction(PyEngineDig),          METH_VARARGS, NULL},
    {"smash",         PyCFunction(PyEngineSmash),        METH_VARARGS, NULL},
    {"applyPalette",  PyCFunction(PyEngineApply),        METH_O,       NULL},
    {"clear",         PyCFunction(PyEngineClearMeth),    METH_NOARGS,  NULL},
    {"flush",         PyCFunction(PyEngineFlush),        METH_NOARGS,  NULL},
    {"on_spawn",      PyCFunction(PyEngineOnSpawn),      METH_VARARGS, NULL},
    {"on_despawn",    PyCFunction(PyEngineOnDespawn),    METH_VARARGS, NULL},
    {"set_animation", PyCFunction(PyEngineSetAnimation), METH_VARARGS, NULL},
    {NULL                                                                  }
};

static PyGetSetDef PyEngineGetset[] = {
    {"lag",         getter(PyEngineLag),         nullptr,                    NULL, NULL},
    {"peak",        getter(PyEnginePeak),        nullptr,                    NULL, NULL},
    {"alive",       getter(PyEngineAlive),       nullptr,                    NULL, NULL},
    {"total",       getter(PyEngineTotal),       nullptr,                    NULL, NULL},
    {"usage",       getter(PyEngineUsage),       nullptr,                    NULL, NULL},
    {"temperature", getter(PyEngineTemperature), nullptr,                    NULL, NULL},
    {"pressure",    getter(PyEnginePressure),    nullptr,                    NULL, NULL},
    {"humidity",    getter(PyEngineHumidity),    nullptr,                    NULL, NULL},
    {"wind",        getter(PyEngineWind),        nullptr,                    NULL, NULL},
    {"density",     getter(PyEngineDensity),     nullptr,                    NULL, NULL},
    {"mach",        getter(PyEngineMach),        nullptr,                    NULL, NULL},
    {"ppo2",        getter(PyEnginePPO2),        nullptr,                    NULL, NULL},
    {"on_trace",    getter(PyEngineGetOnTrace),  setter(PyEngineSetOnTrace), NULL, NULL},
    {"default",     getter(PyEngineGetDefault),  setter(PyEngineSetDefault), NULL, NULL},
    {"water",       getter(PyEngineGetWater),    setter(PyEngineSetWater),   NULL, NULL},
    {NULL                                                                              }
};

PyTypeObject PyEngineType = {
    .ob_base       = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name       = "Engine",
    .tp_basicsize  = sizeof(PyEngine),
    .tp_itemsize   = 0,
    .tp_dealloc    = destructor(PyEngineDealloc),
    .tp_as_mapping = &PyEngineMapping,
    .tp_flags      = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC,
    .tp_traverse   = traverseproc(PyEngineTraverse),
    .tp_clear      = inquiry(PyEngineClear),
    .tp_methods    = PyEngineMethods,
    .tp_getset     = PyEngineGetset,
    .tp_init       = initproc(PyEngineInit),
    .tp_new        = PyEngineNew,
};

void PyEngineReady() {
    PyType_Ready(&PyEngineType);
}
