LLVM_LDFLAGS := $(shell llvm-config --ldflags)
CXXFLAGS := $(shell llvm-config --cxxflags) -Wall -Wno-strict-aliasing \
	$(if $(DEBUG),-O0 -g)
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

.PHONY: build clean
