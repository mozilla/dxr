all: code
code: main.rs
	$(RUSTC) $< -o $@ -L$(@D)
clean:
	rm -rf code *.so

