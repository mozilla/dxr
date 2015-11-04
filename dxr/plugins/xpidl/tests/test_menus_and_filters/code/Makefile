all: obj/nsrootidl.h obj/nsIDownloadHistory.h

obj/%.h: %.idl | obj
	header.py -o $@ --cachedir=obj $^

obj:
	mkdir $@

clean:
	$(RM) -r obj

.PHONY: all clean
