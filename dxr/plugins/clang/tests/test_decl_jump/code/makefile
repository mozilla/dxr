all: code

code: main.o second.o
	$(CXX) -o $@ $^

%.o: %.cpp
	$(CXX) -c -o $@ $<

clean:
	$(RM) code *.o
