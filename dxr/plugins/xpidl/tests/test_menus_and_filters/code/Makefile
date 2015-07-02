all:
	mkdir -p obj
	header.py -o obj/nsrootidl.h --cachedir=obj nsrootidl.idl
	header.py -o obj/nsIDownloadHistory.h --cachedir=obj nsIDownloadHistory.idl
clean:
	rm -rf obj
