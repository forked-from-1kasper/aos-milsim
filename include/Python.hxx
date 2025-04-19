#pragma once

#include "Python.h"

#define RETIFZ(x)     { if ((x) == nullptr)   return;         }
#define RETZIFZ(x)    { if ((x) == nullptr)   return nullptr; }
#define RETERRIFZ(x)  { if ((x) == nullptr)   return -1;      }
#define RETDEFIFZ(x)  { if ((x) == nullptr)   return {};      }
#define RETIFERR()    { if (PyErr_Occurred()) return;         }
#define RETZIFERR()   { if (PyErr_Occurred()) return nullptr; }
#define RETERRIFERR() { if (PyErr_Occurred()) return -1;      }
#define RETDEFIFERR() { if (PyErr_Occurred()) return {};      }

template<typename T> PyObject * PyEncode(T) = delete;

template<> inline PyObject * PyEncode<PyObject *>(PyObject * o)
{ Py_INCREF(o); return o; }

template<> inline PyObject * PyEncode<float>(float f)
{ return PyFloat_FromDouble(f); }

template<> inline PyObject * PyEncode<double>(double d)
{ return PyFloat_FromDouble(d); }

template<> inline PyObject * PyEncode<int>(int d)
{ return PyLong_FromLong(d); }

template<> inline PyObject * PyEncode<long>(long d)
{ return PyLong_FromLong(d); }

template<> inline PyObject * PyEncode<long long>(long long d)
{ return PyLong_FromLongLong(d); }

template<> inline PyObject * PyEncode<unsigned int>(unsigned int d)
{ return PyLong_FromUnsignedLong(d); }

template<> inline PyObject * PyEncode<unsigned long>(unsigned long d)
{ return PyLong_FromUnsignedLong(d); }

template<> inline PyObject * PyEncode<unsigned long long>(unsigned long long d)
{ return PyLong_FromUnsignedLongLong(d); }

template<> inline PyObject * PyEncode<bool>(bool b) {
    PyObject * o = b ? Py_True : Py_False;
    Py_INCREF(o); return o;
}

template<typename T> T PyDecode(PyObject *) = delete;

template<> inline float PyDecode<float>(PyObject * o)
{ return PyFloat_AsDouble(o); }

template<> inline double PyDecode<double>(PyObject * o)
{ return PyFloat_AsDouble(o); }

template<> inline int PyDecode<int>(PyObject * o)
{ return PyLong_AsLong(o); }

template<> inline long PyDecode<long>(PyObject * o)
{ return PyLong_AsLong(o); }

template<> inline long long PyDecode<long long>(PyObject * o)
{ return PyLong_AsLongLong(o); }

template<> inline unsigned int PyDecode<unsigned int>(PyObject * o)
{ return PyLong_AsUnsignedLong(o); }

template<> inline unsigned long PyDecode<unsigned long>(PyObject * o)
{ return PyLong_AsUnsignedLong(o); }

template<> inline unsigned long long PyDecode<unsigned long long>(PyObject * o)
{ return PyLong_AsUnsignedLongLong(o); }

template<> inline bool PyDecode<bool>(PyObject * o)
{ return o == Py_True; }

template<typename... Ts, size_t... Is>
inline PyObject * newPyTuple(std::index_sequence<Is...>, Ts... ts) {
    PyObject * value = PyTuple_New(sizeof...(Ts));
    (PyTuple_SET_ITEM(value, Is, PyEncode<Ts>(ts)), ...);

    return value;
}

template<typename... Ts> struct PyTuple {
    PyObject * value;

    inline operator PyObject *() const { return value; }

    inline PyTuple(Ts... ts) { value = newPyTuple<Ts...>(std::index_sequence_for<Ts...>(), ts...); }
    inline ~PyTuple() { Py_DECREF(value); }
};

template<typename... Ts> inline PyObject * PyApply(PyObject * funval, Ts... ts)
{ return PyObject_Call(funval, PyTuple(ts...), NULL); }

class PyOwnedRef {
    PyObject * ref;
public:
    inline PyOwnedRef() : ref(nullptr) {}

    inline PyOwnedRef(PyObject * o) : ref(o) { }

    inline PyOwnedRef(PyObject * o, const char * attr)
    { ref = PyObject_GetAttrString(o, attr); }

    inline ~PyOwnedRef() { Py_XDECREF(ref); }

    PyOwnedRef(const PyOwnedRef &) = delete;

    PyOwnedRef & operator=(const PyOwnedRef &) = delete;

    inline PyOwnedRef(PyOwnedRef && rvalue) {
        ref = rvalue.ref;
        rvalue.ref = nullptr;
    };

    inline PyOwnedRef & operator=(PyOwnedRef && rvalue) {
        if (this != &rvalue) {
            Py_XDECREF(ref);
            ref = rvalue.ref;
            rvalue.ref = nullptr;
        }

        return *this;
    };

    inline operator PyObject *() const { return ref; }

    template<typename... Ts> inline auto operator()(Ts... ts) const
    { return PyOwnedRef(ref == nullptr ? nullptr : PyApply<Ts...>(ref, ts...)); }

    inline PyObject * incref() const { Py_XINCREF(ref); return ref; }

    inline void retain(PyObject * o) { Py_XDECREF(ref); Py_XINCREF(o); ref = o; }
};

template<typename T> inline T PyGetAttr(PyObject * o, const char * attr) {
    PyOwnedRef attrval(o, attr); RETDEFIFZ(attrval);

    return PyDecode<T>(attrval);
}

template<typename T> inline T PyGetAttr(PyObject * o, const char * attr, const T defval) {
    PyOwnedRef attrval(o, attr);
    if (attrval == nullptr) return defval;

    return PyDecode<T>(attrval);
}

template<typename T> inline T PyGetItem(PyObject * o, const char * k) {
    auto val = PyDict_GetItemString(o, k); RETDEFIFZ(val);

    return PyDecode<T>(val);
}

template<typename T> inline T PyGetItem(PyObject * o, const char * k, const T defval) {
    auto val = PyDict_GetItemString(o, k);
    if (val == nullptr) return defval;

    return PyDecode<T>(val);
}
