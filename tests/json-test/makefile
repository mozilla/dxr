all:
	cat test.config.in | sed -e 's?PWD?'`pwd`'?g' > test.config
	cd ../../; ./update.sh tests/json-test/test.config HelloWorld; cd -
clean:
	rm -rf test.config
	rm -rf HelloWorld-obj
	rm -rf www
	cd HelloWorld; make clean; cd -
