LLVM_LIBS := $(shell llvm-config --libdir)
CXXFLAGS := $(shell llvm-config --cflags) -Wall \
	-fno-exceptions -fno-rtti \
	-I$(shell llvm-config --includedir)
LDFLAGS := -fPIC -g -Wl,-R -Wl,'$$ORIGIN' -L$(LLVM_LIBS) -shared

prebuild: libclang-index-plugin.so

can-use:
	@if [ -z "$$(which llvm-config)" -o \
			! -d $(shell llvm-config --includedir) ]; then \
		echo "no"; \
	else \
		echo "yes"; \
	fi

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $^ -o $@

libclang-index-plugin.so: dxr-index.o sha1.o
	$(CXX) $(LDFLAGS) $^ -o $@ -shared

clean:
	rm -rf *.o libclang-index-plugin.so
