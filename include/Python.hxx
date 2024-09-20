#pragma once

#include "Python.h"

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

template<> inline PyObject * PyEncode<bool>(bool b)
{ return b ? Py_True : Py_False; }

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

    PyTuple(Ts... ts) { value = newPyTuple<Ts...>(std::index_sequence_for<Ts...>(), ts...); }
    ~PyTuple() { Py_DECREF(value); }
};

class PyOwnedRef {
    PyObject * ref;
public:
    PyOwnedRef(PyObject * o) : ref(o) {}

    PyOwnedRef(PyObject * o, const char * attr)
    { ref = PyObject_GetAttrString(o, attr); }

    ~PyOwnedRef() { Py_XDECREF(ref); }

    inline void invalidate() { ref = nullptr; }

    inline operator PyObject *() const { return ref; }

    PyOwnedRef(const PyOwnedRef &) = delete;
    PyOwnedRef & operator=(const PyOwnedRef &) = delete;
};

template<typename... Ts> inline PyObject * PyApply(PyObject * funval, Ts... ts)
{ return PyObject_Call(funval, PyTuple(ts...), NULL); }

template<typename T> inline T PyGetAttr(PyObject * o, const char * attr) {
    PyOwnedRef attrval(o, attr);

    if (attrval == nullptr)
        return {};
    else
        return PyDecode<T>(attrval);
}

inline void PyRetain(PyObject * & member, PyObject * const o)
{ Py_XDECREF(member); Py_XINCREF(o); member = o; }
