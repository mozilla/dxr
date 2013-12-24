all: code  
crate2: crate2.rs
	$(RUST) $< -o $@
code: main.rs crate2
	$(RUST) -L$(@D) $< -o $@
clean:
	rm -rf code

