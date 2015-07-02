all:
	mkdir -p obj/dist/include
	header.py -o obj/dist/include/nsrootidl.h --cachedir=obj base/nsrootidl.idl
	header.py -o obj/dist/include/nsISupports.h --cachedir=obj nsISupports.idl -Ibase
	header.py -o obj/dist/include/nsITableEditor.h --cachedir=obj nsITableEditor.idl -Ibase
clean:
	rm -rf obj/*
