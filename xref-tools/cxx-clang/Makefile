LLVM_LIBS := $(shell llvm-config --libdir)
CXXFLAGS := -Wall -Werror -g -I$(shell llvm-config --includedir) \
	-D__STDC_LIMIT_MACROS -D__STDC_CONSTANT_MACROS -fPIC -fno-exceptions -fno-rtti
LDFLAGS := -fPIC -g -Wl,-R -Wl,'$$ORIGIN' -L$(LLVM_LIBS) -shared

prebuild: libclang-index-plugin.so

can-use:
	@if [ -z "$$(which llvm-config)" -o \
			! -d $$(llvm-config --includedir)/clang ]; then \
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
