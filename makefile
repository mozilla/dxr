PLUGINS = clang pygmentize

BUILD_PLUGINS = $(PLUGINS:%=build-plugin-%)
CHECK_PLUGINS = $(PLUGINS:%=check-plugin-%)
CLEAN_PLUGINS = $(PLUGINS:%=clean-plugin-%)

all: build

test:

build: $(BUILD_PLUGINS) trilite

check: $(CHECK_PLUGINS) trilite

clean: $(CLEAN_PLUGINS) trilite-clean

trilite:
	$(MAKE) -C trilite/ release

trilite-clean:
	$(MAKE) -C trilite/ clean

$(BUILD_PLUGINS):
	$(MAKE) -C $(@:build-plugin-%=plugins/%) build

$(CHECK_PLUGINS):
	$(MAKE) -C $(@:check-plugin-%=plugins/%) check

$(CLEAN_PLUGINS):
	$(MAKE) -C $(@:clean-plugin-%=plugins/%) clean


.PHONY: $(BUILD_PLUGINS)
.PHONY: $(CHECK_PLUGINS)
.PHONY: $(CLEAN_PLUGINS)
.PHONY: all build check clean test trilite trilite-clean
