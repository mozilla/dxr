FILES := $(wildcard *.cpp *.c)

build: $(basename $(FILES))


%: %.cpp 
	$(CXX) -c -o $@ $<

%: %.c
	$(CC) -c -o $@ $<

clean:
	rm -rf $(basename $(FILES)) *.csv web
