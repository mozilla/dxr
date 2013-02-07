all: HelloWorld
HelloWorld: main.c const_overload.cpp prototype_parameter.cpp static_member.cpp \
            typedef.cpp member_function.cpp member_variable.cpp \
            macro_ifdef.cpp macro_ifndef.cpp macro_undef.cpp macro_if_defined.cpp
	$(CXX) -o $@ $^
clean:
	rm -rf HelloWorld
