all:
	cat test.config.in | sed -e 's?PWD?'`pwd`'?g' > test.config
	cd ../../; ./dxr-build.py --file tests/json-test/test.config; cd -
clean:
	rm -rf test.config
	rm -rf HelloWorld-objects
	rm -rf temp
	rm -rf target
	cd HelloWorld; make clean; cd -
