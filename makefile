PLUGINS ?= clang

BUILD_PLUGINS = $(PLUGINS:%=build-plugin-%)
CHECK_PLUGINS = $(PLUGINS:%=check-plugin-%)
CLEAN_PLUGINS = $(PLUGINS:%=clean-plugin-%)

all: build

test: build
	python setup.py test

build: $(BUILD_PLUGINS) templates pycs

node:
	npm install

pycs:
	find . -name "*.pyc" -exec rm -f {} \;

templates: node
	node_modules/.bin/grunt precompile

$(BUILD_PLUGINS):
	$(MAKE) -C $(@:build-plugin-%=dxr/plugins/%) build

$(CHECK_PLUGINS):
	$(MAKE) -C $(@:check-plugin-%=dxr/plugins/%) check

$(CLEAN_PLUGINS):
	$(MAKE) -C $(@:clean-plugin-%=dxr/plugins/%) clean


.PHONY: $(BUILD_PLUGINS)
.PHONY: $(CHECK_PLUGINS)
.PHONY: $(CLEAN_PLUGINS)
.PHONY: all build check clean test pycs node
