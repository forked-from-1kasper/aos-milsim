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
HXXFILES     = $(shell find $(INCLUDEDIR) -type f -name '*.hxx')

all: hier $(DYNLIBNAME)

$(BUILDDIR)/simulator.c: $(SOURCEDIR)/simulator.pyx $(HXXFILES)
	$(CYTHON) -3 $< -o $@

$(BUILDDIR)/simulator.o: $(BUILDDIR)/simulator.c
	$(CXX) -c $(CXXFLAGS) $^ -o $@

$(DYNLIBNAME): $(BUILDDIR)/simulator.o
	$(CXX) $(LDFLAGS) $^ -o $@

hier:
	mkdir -p $(BUILDDIR)

clean:
	rm -rf $(BUILDDIR)/*.o $(BUILDDIR)/*.c $(DYNLIBNAME)