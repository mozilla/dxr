LEX		?= flex
CC		?= gcc
CFLAGS	:= $(shell pkg-config --cflags sqlite3) -DSQLITE_ENABLE_FTS3 -Wall -DNDEBUG
LDFLAGS := $(shell pkg-config --libs sqlite3)
all: build
build: libdxr-code-tokenizer.so
lex.yy.c: dxr-tokenizer.yy
	$(LEX) $<
libdxr-code-tokenizer.so: lex.yy.c
	$(CC) $(CFLAGS) $< $(LDFLAGS) -o $@ -shared -fPIC
test: lex.yy.c
	$(CC) -g $(CFLAGS) -DTEST $< $(LDFLAGS) -o $@
	chmod +x $@
check: test
	./test
clean:
	rm -rf libdxr-code-tokenizer.so test lex.yy.c
