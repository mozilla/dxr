CXXFLAGS := -std=c++11 # for class enums

all: code

code: main.o foo.o template_foo.o
	$(CXX) -o $@ $^

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $^

clean:
	rm -f code *.o
