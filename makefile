PLUGINS = clang pygmentize

BUILD_PLUGINS = $(PLUGINS:%=build-plugin-%)
CHECK_PLUGINS = $(PLUGINS:%=check-plugin-%)
CLEAN_PLUGINS = $(PLUGINS:%=clean-plugin-%)

all: build


build: $(BUILD_PLUGINS)

check: $(CHECK_PLUGINS)

clean: $(CLEAN_PLUGINS)


$(BUILD_PLUGINS):
	$(MAKE) -C $(@:build-plugin-%=plugins/%) build

$(CHECK_PLUGINS): 
	$(MAKE) -C $(@:check-plugin-%=plugins/%) check

$(CLEAN_PLUGINS): 
	$(MAKE) -C $(@:clean-plugin-%=plugins/%) clean


.PHONY: $(BUILD_PLUGINS)
.PHONY: $(CHECK_PLUGINS)
.PHONY: $(CLEAN_PLUGINS)
.PHONY: all build check clean
