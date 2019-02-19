LLVM_CONFIG ?= llvm-config
LLVM_LDFLAGS := $(shell ${LLVM_CONFIG} --ldflags)
ifeq ($(LLVM_LDFLAGS),)
$(error Could not run $(LLVM_CONFIG).  Please make sure it is available on your PATH \
or specify the absolute path of the llvm-config executable in the LLVM_CONFIG environment variable)
endif
CXXFLAGS := $(shell ${LLVM_CONFIG} --cxxflags) -fPIC -O2 -std=c++11 -Wall -Wno-strict-aliasing $(if $(DEBUG),-O0 -g)
LDFLAGS := -fPIC -g -Wl,-R -Wl,'$$ORIGIN' $(LLVM_LDFLAGS) -shared

build: libclang-index-plugin.so

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $^ -o $@

libclang-index-plugin.so: dxr-index.o sha1.o
	$(CXX) $(LDFLAGS) $^ -o $@

check: build
	which clang
	which clang++

clean:
	$(RM) *.o libclang-index-plugin.so

.PHONY: build check clean
