PYTHON       = python3
PYTHONCONFIG = python3-config
CXX          = c++
CYTHON       = cython
LIBPYSPADES  = $(shell $(PYTHON) -m site --user-site)/pyspades
CXXFLAGS     = -pthread -std=c++23 -fPIC -Ibuild/ -Iinclude/ -I$(LIBPYSPADES) $(shell $(PYTHONCONFIG) --includes)
LDFLAGS      = -pthread -shared

all: build

build:
	mkdir -p build

clean:
	rm -f build/*.o build/*.h build/*.cxx milsim/*.so

release: CXXFLAGS += -O3
release: all

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

all: milsim/ctypes.so milsim/packets.so milsim/simulator.so milsim/vxl.so

build/simulator.h: build/simulator.o

build/ctypes.o:
build/packets.o:
build/vxl.o: include/VXL.hxx
build/simulator.o: include/Milsim/PyEngine.hxx
build/Engine.o: include/Milsim/Engine.hxx
build/PyEngine.o: include/Milsim/Engine.hxx include/Milsim/PyEngine.hxx
build/VXL.o: include/VXL.hxx

milsim/vxl.so: build/VXL.o
milsim/simulator.so: build/PyEngine.o build/Engine.o

include/Milsim/AABB.hxx: include/Milsim/Vector.hxx
include/Milsim/Engine.hxx: build/simulator.h include/Python.hxx include/Milsim/Vector.hxx include/Milsim/AABB.hxx include/Milsim/Fundamentals.hxx
include/Milsim/Fundamentals.hxx: include/Milsim/Vector.hxx include/Milsim/AABB.hxx
include/Milsim/PyEngine.hxx: include/Milsim/Fundamentals.hxx include/Python.hxx
include/Milsim/Vector.hxx:

include/Python.hxx:
include/VXL.hxx: include/Milsim/Vector.hxx
