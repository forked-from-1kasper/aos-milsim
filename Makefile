PYTHON       = python3
PYTHONCONFIG = python3-config
CXX          = c++
CYTHON       = cython
CXXFLAGS     = -pthread -fPIC -std=c++23 -Wno-mathematical-notation-identifier-extension -Ibuild/ -Iinclude/ -I$(LIBPYSPADES) $(shell $(PYTHONCONFIG) --includes)
LDFLAGS      = -pthread -shared
PYMODCMD     = 'from importlib.util import find_spec; print(find_spec("pyspades").origin)'
LIBPYSPADES  = $(shell dirname `$(PYTHON) -c $(PYMODCMD)`)

debug: CXXFLAGS += -g
debug: all

release: CXXFLAGS += -O3
release: all

all: build

build:
	mkdir -p build

clean:
	rm -f build/*.o build/*.h build/*.cxx milsim/*.so

build/%.cxx: source/%.pyx
	$(CYTHON) --cplus -3 $< -o $@

build/%.o: build/%.cxx
	$(CXX) -c $(CXXFLAGS) $< -o $@

build/%.o: source/%.cxx
	$(CXX) -c $(CXXFLAGS) $< -o $@

milsim/%.so: build/%.o
	$(CXX) $(LDFLAGS) $^ -o $@

%.hxx:
	touch $@

all: milsim/packets.so milsim/engine.so milsim/vxl.so

build/engine.h: build/engine.o

build/packets.o:
build/vxl.o: include/VXL.hxx
build/engine.o: include/Milsim/PyEngine.hxx
build/Engine.o: include/Milsim/Engine.hxx
build/PyEngine.o: include/Milsim/Engine.hxx include/Milsim/PyEngine.hxx
build/VXL.o: include/VXL.hxx

milsim/vxl.so: build/VXL.o
milsim/engine.so: build/PyEngine.o build/Engine.o

include/Milsim/AABB.hxx: include/Milsim/Vector.hxx
include/Milsim/Engine.hxx: build/engine.h include/Python.hxx include/Milsim/Vector.hxx include/Milsim/AABB.hxx include/Milsim/Fundamentals.hxx
include/Milsim/Fundamentals.hxx: include/Milsim/Vector.hxx include/Milsim/AABB.hxx
include/Milsim/PyEngine.hxx: include/Milsim/Fundamentals.hxx include/Python.hxx
include/Milsim/Vector.hxx:

include/Python.hxx:
include/VXL.hxx: include/Milsim/Vector.hxx
