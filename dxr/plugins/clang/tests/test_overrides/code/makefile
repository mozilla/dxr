all: code

code: main.o base.o derived.o
	$(CXX) -o $@ $^

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $^

clean:
	rm -f code *.o
