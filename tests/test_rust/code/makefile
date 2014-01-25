all: code  
krate2: krate2.rs
	$(RUST) $< -o $@
code: main.rs krate2
	$(RUST) -L$(@D) $< -o $@
clean:
	rm -rf code *.so

