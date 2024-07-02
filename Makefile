PYTHON       ?= python3
PYTHONCONFIG ?= python3-config
CXX          ?= c++
CYTHON       ?= cython
LIBPYSPADES  ?= $(shell $(PYTHON) -m site --user-site)/pyspades
SOURCEDIR     = source
INCLUDEDIR    = include
BUILDDIR      = build
DYNLIBNAME    = milsim/simulator.so
HXXFILES      = $(shell find $(INCLUDEDIR) -type f -name '*.hxx')
CXXFLAGS      = -pthread -std=c++23 -fPIC -I$(INCLUDEDIR) -I$(LIBPYSPADES) $(shell $(PYTHONCONFIG) --includes)
LDFLAGS       = -pthread -shared

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
