all:
	# Link paths in test.config.in to current working directory
	# replaces PWD with `pwd` and produces test.config
	cat test.config.in | sed -e 's?PWD?'`pwd`'?g' > test.config
	# Navigate into the DXR folder, build using config file
	LD_LIBRARY_PATH=$$LD_LIBRARY_PATH:../../trilite dxr-build.py test.config
	# Launch test server at port 8000:
	# ../../bin/dxr-serve.py target
clean:
	rm -rf test.config
	rm -rf HelloWorld-objects
	rm -rf temp
	rm -rf target
	cd HelloWorld; make clean; cd -
