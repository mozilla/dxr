all: code
krate: krate.rs
	$(RUSTC) $< 
code: main.rs krate
	$(RUSTC) $< -o $@ -L$(@D)
clean:
	rm -rf code *.so
