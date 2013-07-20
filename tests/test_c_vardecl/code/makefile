all: code
code: main.o extern.o
	$(CXX) -o $@ $^

main.o: main.cpp extern.h
	$(CXX) -I. -c main.cpp

extern.o: extern.c extern.h
	$(CC) -I. -c extern.c

clean:
	rm -rf code *.o
