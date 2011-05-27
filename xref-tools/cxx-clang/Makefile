LLVM_INCLUDES := $(shell llvm-config --includedir)
LLVM_LIBS := $(shell llvm-config --libdir)
CXXFLAGS := -Wall -g -I$(LLVM_INCLUDES)
LDFLAGS := -L$(LLVM_LIBS) -Wl,-rpath,$(LLVM_LIBS) -llibclang -lstdc++

%.o: %.cpp
	$(CXX) -c $(CXXFLAGS) -o $@ $^

clang-dump-sql: dxr-index.o
	$(CXX) $(LDFLAGS) -o $@ $^

clean:
	rm -rf *.o clang-dump-sql
