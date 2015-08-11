all: obj/nsISupports.h obj/nsITableEditor.h

obj/%.h: %.idl | obj
	header.py -o $@ --cachedir=obj $^ -Ibase

obj:
	mkdir $@

clean:
	$(RM) -r obj

.PHONY: all clean
