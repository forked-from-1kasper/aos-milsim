#pragma once

#include "Python.h"

template<typename T> PyObject * newPyObject(T) = delete;

template<> inline PyObject * newPyObject<PyObject *>(PyObject * o)
{ Py_INCREF(o); return o; }

template<> inline PyObject * newPyObject<float>(float f)
{ return PyFloat_FromDouble(f); }

template<> inline PyObject * newPyObject<double>(double d)
{ return PyFloat_FromDouble(d); }

template<> inline PyObject * newPyObject<int>(int d)
{ return PyLong_FromLong(d); }

template<> inline PyObject * newPyObject<long>(long d)
{ return PyLong_FromLong(d); }

template<> inline PyObject * newPyObject<long long>(long long d)
{ return PyLong_FromLongLong(d); }

template<> inline PyObject * newPyObject<unsigned int>(unsigned int d)
{ return PyLong_FromUnsignedLong(d); }

template<> inline PyObject * newPyObject<unsigned long>(unsigned long d)
{ return PyLong_FromUnsignedLong(d); }

template<> inline PyObject * newPyObject<unsigned long long>(unsigned long long d)
{ return PyLong_FromUnsignedLongLong(d); }

template<typename... Ts, size_t... Is>
inline PyObject * newPyTuple(std::index_sequence<Is...>, Ts... ts) {
    PyObject * value = PyTuple_New(sizeof...(Ts));
    (PyTuple_SET_ITEM(value, Is, newPyObject<Ts>(ts)), ...);

    return value;
}

template<typename... Ts> struct PyTuple {
    PyObject * value;

    inline operator PyObject *() const { return value; }

    PyTuple(Ts... ts) { value = newPyTuple<Ts...>(std::index_sequence_for<Ts...>(), ts...); }
    ~PyTuple() { Py_DECREF(value); }
};

template<typename... Ts> inline PyObject * PyApply(PyObject * funval, Ts... ts)
{ return PyObject_Call(funval, PyTuple(ts...), NULL); }
