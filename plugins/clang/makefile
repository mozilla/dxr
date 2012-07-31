LLVM_LIBS := $(shell llvm-config --libdir)
CXXFLAGS := $(shell llvm-config --cflags) -Wall \
	-fno-exceptions -fno-rtti \
	-I$(shell llvm-config --includedir)
LDFLAGS := -fPIC -g -Wl,-R -Wl,'$$ORIGIN' -L$(LLVM_LIBS) -shared

build: libclang-index-plugin.so

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $^ -o $@

libclang-index-plugin.so: dxr-index.o sha1.o
	$(CXX) $(LDFLAGS) $^ -o $@ -shared

clean:
	rm -rf *.o libclang-index-plugin.so

.PHONY: build clean
