CFLAGS := `pkg-config --cflags sqlite3` -DSQLITE_ENABLE_FTS3 -Wall
LDFLAGS := `pkg-config --libs sqlite3`

%.o: %.c
	$(CC) $(CFLAGS) -c $^ -o $@ -fPIC

libdxr-code-tokenizer.so: code-tokenizer.o
	$(CC) $^ $(LDFLAGS) -o $@ -shared

clean:
	rm -rf *.o libdxr-code-tokenizer.so
