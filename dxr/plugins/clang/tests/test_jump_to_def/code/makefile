all: code

code: main.o foo.o
	$(CXX) -o code $^

%.o: %.cpp
	$(CXX) -c -o $@ $<

clean:
	rm -rf code *.o
