all: code
code: main.c const_overload.cpp prototype_parameter.cpp typedef.cpp \
            macro_ifdef.cpp macro_ifndef.cpp macro_undef.cpp macro_if_defined.cpp
	$(CXX) -o $@ $^
clean:
	rm -rf code
