all: code

code: Z.o main.o
	$(CXX) -o $@ $^

%.o: %.cpp
	$(CXX) -c -o $@ $^

clean:
	rm -rf code *.o
