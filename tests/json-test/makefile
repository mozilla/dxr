all:
	# Link paths in test.config.in to current working directory
	# replaces PWD with `pwd` and produces test.config
	cat test.config.in | sed -e 's?PWD?'`pwd`'?g' > test.config
	# Navigate into the DXR folder, build using config file
	cd ../../; LD_LIBRARY_PATH=`pwd`/trilite ./dxr-build.py --file tests/json-test/test.config; cd -
	# Launch test server at port 8000
	# cd target/server; ./test-server.py --port 8000; cd - 
clean:
	rm -rf test.config
	rm -rf HelloWorld-objects
	rm -rf temp
	rm -rf target
	cd HelloWorld; make clean; cd -
