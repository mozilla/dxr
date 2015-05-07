
PLUGINS ?= clang

BUILD_PLUGINS = $(PLUGINS:%=build-plugin-%)
CHECK_PLUGINS = $(PLUGINS:%=check-plugin-%)
CLEAN_PLUGINS = $(PLUGINS:%=clean-plugin-%)

PWD = $(shell pwd)

help:
	@echo "Please use 'make <target>' where <target> is one of"
	@echo "  all: build dxr"
	@echo "  test: build and test dxr"
	@echo "  build: build dxr, generate templates, clean up pyc files"
	@echo "  docker: create docker images and provision dxr dev application"
	@echo "  docker-dxrdev setup dxr for docker based development"
	@echo "  docker-images rebuild docker images"
	@echo "  node: run npm install to get things like grunt"
	@echo "  pycs: clean up .pyc files"
	@echo "  templates: use grunt to precompile dxr templates"

all: build

test: build
	python setup.py test

build: $(BUILD_PLUGINS) templates pycs

docker: docker-images docker-dxrdev

docker-dxrdev:
	docker run --rm -v $(PWD):/home/dxr/ mozilla/dxr_application setup_dxr
	@cp dockerfiles/docker-compose.yml.template docker-compose.yml
	@echo "    - $(PWD):/dxr\n" >> docker-compose.yml

docker-images:
	docker pull --all-tags=false elasticsearch:1.4 2>&1 |grep -e Pulling -e Status
	docker pull --all-tags=false ubuntu:14.04 2>&1 |grep -e Pulling -e Status
	docker build --rm -t mozilla/dxr_elasticsearch dockerfiles/elasticsearch
	docker build --rm -t mozilla/dxr_application dockerfiles/dxr

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
.PHONY: all build check clean docker docker-dxrdev docker-images test pycs node
