PYTHON      ?= python3.10
CXX         ?= c++
CYTHON      ?= cython
LIBPYSPADES ?= $(HOME)/.local/lib/$(PYTHON)/site-packages/pyspades/
LIBPYTHON   ?= /usr/include/$(PYTHON)
CXXFLAGS     = -pthread -std=c++23 -fPIC -I$(INCLUDEDIR) -I$(LIBPYSPADES) -I$(LIBPYTHON)
LDFLAGS      = -pthread -shared
SOURCEDIR    = source
INCLUDEDIR   = include
BUILDDIR     = build
DYNLIBNAME   = milsim/simulator.so

all: hier
	$(CYTHON) -3 $(SOURCEDIR)/simulator.pyx -o $(BUILDDIR)/simulator.c
	$(CXX) -c $(CXXFLAGS) $(BUILDDIR)/simulator.c -o $(BUILDDIR)/simulator.o
	$(CXX) $(LDFLAGS) $(BUILDDIR)/simulator.o -o $(DYNLIBNAME)

hier:
	mkdir -p $(BUILDDIR)

clean:
	rm -rf $(BUILDDIR)/*.o $(BUILDDIR)/*.c $(DYNLIBNAME)