TESTS := $(shell sed -e '/^\[/!d' -e 's/\[\|\]//g' tests.ini)

check: $(addprefix check-,$(TESTS))
check-%: %
	./run-test.sh $*

clean: $(addprefix clean-,$(TESTS))
clean-%:
	make -C $* clean
