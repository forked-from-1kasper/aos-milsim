PYTHON       = python3
PYTHONCONFIG = python3-config
CXX          = c++
CYTHON       = cython
LIBPYSPADES  = $(shell $(PYTHON) -m site --user-site)/pyspades
SOURCEDIR    = source
INCLUDEDIR   = include
BUILDDIR     = build
LIBDIR       = milsim
CXXFLAGS     = -pthread -std=c++23 -fPIC -I$(INCLUDEDIR) -I$(LIBPYSPADES) $(shell $(PYTHONCONFIG) --includes)
LDFLAGS      = -pthread -shared
MODULES      = simulator vxl packets
HXXFILES     = $(shell find $(INCLUDEDIR) -type f -name '*.hxx')
DYNLIBS      = $(MODULES:%=$(LIBDIR)/%.so)

all: hier $(DYNLIBS)

$(BUILDDIR)/%.c: $(SOURCEDIR)/%.pyx $(HXXFILES)
	$(CYTHON) -3 $< -o $@

$(BUILDDIR)/%.o: $(BUILDDIR)/%.c
	$(CXX) -c $(CXXFLAGS) $^ -o $@

$(LIBDIR)/%.so: $(BUILDDIR)/%.o
	$(CXX) $(LDFLAGS) $^ -o $@

hier:
	mkdir -p $(BUILDDIR)

clean:
	rm -rf $(BUILDDIR)/*.o $(BUILDDIR)/*.c $(DYNLIBS)
