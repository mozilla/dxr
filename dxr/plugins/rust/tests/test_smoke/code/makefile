all: code
krate2: krate2.rs
	$(RUSTC) $< 
code: main.rs krate2
	$(RUSTC) $< -o $@ -L$(@D)
clean:
	rm -rf code *.so
