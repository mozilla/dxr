all: c
	mkdir code
	cd code && python -c "import os; os.mkdir('\x8d\xae\xa2\xa0\xef')"
	cd code && python -c "open('\x8d\xae\xa2\xa0\xef/\xaf\xa0\xaf\xaa\xa0', 'w').write('Hello!\n')"
	@# Invalid UTF-8:
	cd code && python -c "from os import mkdir; mkdir('a\xc3\x28')"
	cd code && python -c "open('b\xc3\x28', 'w').write('Hello!\n')"
c: 第一.c
	$(CXX) -o $@ $^
clean:
	rm -rf code
