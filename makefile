# Things you might normally want to run:

## These are meant to be run within whatever virtualized, containerized, or
## (heaven forbid) bare-metal environment contains DXR:

all: static plugins requirements .dxr_installed

test: all
	python setup.py test

clean: static_clean
	rm -rf node_modules/.bin/nunjucks-precompile \
	       node_modules/nunjucks \
	       .npm_installed \
	       .peep_installed \
	       venv \
	       .dxr_dev_image_built \
	       .dxr_installed
	find . -name "*.pyc" -exec rm -f {} \;
	$(MAKE) -C dxr/plugins/clang clean

static_clean:
	rm -rf dxr/static_unhashed/js/templates.js \
	       dxr/build \
	       dxr/static \
	       dxr/static_manifest

# Cache-bust static assets:
static: dxr/static_manifest

docs: requirements .dxr_installed
	$$VIRTUAL_ENV/bin/pip install Sphinx==1.3.1
	$(MAKE) -C docs html

# Install dev conveniences:
dev:
	$$VIRTUAL_ENV/bin/pip install pdbpp nose-progressive


## Conveniences to run from your host machine if running DXR in Docker:

# NEXT: "make docker_test" works, except a few tests fail, because the ES image is broken. It's not enabling dynamic scripting atm. Then figure out how to get the ES image built and when to run it. Maybe docker-compose can help. Get ES image putting data on a volume so it persists (its dockerfile already says it should). Call docker-machine automatically on Mac.

docker_es: docker_machine
	# TODO: Put ES data on a volume so it persists across containers.
	cd docker_es; docker build -t dxr_es .; docker rm -f dxr_es || true; docker run -d --name dxr_es -p 80:8000 dxr_es

shell: .dxr_dev_image_built docker_machine
	docker run --rm -ti -v $(PWD):/home/dxr/dxr --net container:dxr_es --tty --name dxr_dev dxr_dev bash
	#/home/dxr/venv/bin/nosetests --with-progressive ${TESTS}

# Run tests from outside Docker, like for CI:
docker_test: .dxr_dev_image_built
	docker run --rm -v $(PWD):/home/dxr/dxr --net container:dxr_es --tty --name dxr_dev dxr_dev make test

docker_clean:
	docker rm -f dxr_dev || true
	rm .dxr_dev_image_built



# Private things:

# If there's an activated virtualenv, use that. Otherwise, make one in the cwd.
# This lets the installed Python packages persist across container runs when
# using Docker.
VIRTUAL_ENV ?= $(PWD)/venv
DXR_PROD ?= 0

docker_machine:
	#docker-machine env default || docker-machine create --driver virtualbox --virtualbox-disk-size 50000 --virtualbox-cpu-count 4 --virtualbox-memory 256 default

.dxr_dev_image_built: Dockerfile docker/set_up_common.sh docker/set_up_ubuntu.sh
	docker build -t dxr_dev .
	touch $@

# Make a virtualenv at $VIRTUAL_ENV if there isn't one. DXR assumes you're
# using a venv. If you don't specify an external venv, we reason that, after
# creating one for you, you'll need Python packages installed.
$(VIRTUAL_ENV)/bin/activate:
	virtualenv $(VIRTUAL_ENV)
	rm -f .peep_installed .dxr_installed

# Install DXR into the venv. Reinstall it if the setuptools entry points may
# have changed. To install it in non-editable mode, set DXR_PROD=1 in the
# environment.
.dxr_installed: $(VIRTUAL_ENV)/bin/activate setup.py
ifeq ($(DXR_PROD),1)
	$$VIRTUAL_ENV/bin/pip install --no-deps .
else
	$$VIRTUAL_ENV/bin/pip install --no-deps -e .
endif
	touch $@

# Install Python requirements:
requirements: $(VIRTUAL_ENV)/bin/activate .peep_installed

plugins:
	$(MAKE) -C dxr/plugins/clang

dxr/static_unhashed/js/templates.js: dxr/templates/nunjucks/*.html \
	                                 .npm_installed
	node_modules/.bin/nunjucks-precompile dxr/templates/nunjucks > $@

# .npm_installed is an empty file we touch whenever we run npm install. This
# target redoes the install if the packages or lockdown files are newer than
# that file:
.npm_installed: package.json lockdown.json
	npm install
	touch $@

# Install requirements in current virtualenv:
.peep_installed: requirements.txt
	$$VIRTUAL_ENV/bin/python peep.py install -r requirements.txt
	touch $@

# Static-file cachebusting:

SRC_DIR := dxr/static_unhashed
DST_DIR := dxr/static
TMP_DIR := dxr/build
# Static files that don't refer to any others. Lazy-compute so we can pick up
# the generated templates.js.
LEAVES = $(shell find $(SRC_DIR) -type f ! -name '.DS_Store' ! -name '*.css')
# CSS files do refer to other static files, via url(...):
CSS := $(shell find $(SRC_DIR) -type f -name '*.css')
CSS_TEMPS := $(addprefix $(TMP_DIR)/,$(notdir $(shell find $(SRC_DIR)/css -name '*.css')))

# We kick out lines like "abcde12345 somefile.ext", then pass those args, in
# pairs, to sed, to construct the manifest lines, which look like
# "fonts/icons.eot fonts/icons.383e693f.eot".
dxr/build/leaf_manifest: $(LEAVES) dxr/static_unhashed/js/templates.js
	# Building leaf-asset submanifest...
	mkdir -p $(@D)
	echo $(LEAVES) | xargs -n1 -I% sh -c 'md5sum %' \
	               | xargs -n2 \
	               | sed 's|\(........\)[a-f0-9]* $(SRC_DIR)/\([^.]*\)\.\(.*\)|\2.\3 \2.\1.\3|' \
	               > $@

# Copy the CSS files to build/*.css and substitute their references.
# See https://www.gnu.org/software/make/manual/html_node/Static-Usage.html
$(CSS_TEMPS): $(TMP_DIR)/%.css: $(SRC_DIR)/css/%.css dxr/build/leaf_manifest
	./replace_urls.py dxr/build/leaf_manifest $< > $@

dxr/build/css_manifest: $(CSS_TEMPS)
	# Building CSS submanifest...
	echo $(CSS_TEMPS) | xargs -n1 -I% sh -c 'md5sum %' \
	                  | xargs -n2 \
	                  | sed 's|\(........\)[a-f0-9]* $(TMP_DIR)/\([^.]*\)\.\(.*\)|css/\2.\3 css/\2.\1.\3|' \
	                  > $@

# Add CSS hashes to those already in leaf_manifest:
dxr/static_manifest: $(CSS_TEMPS) dxr/build/leaf_manifest dxr/build/css_manifest
	# Copying CSS files to hashed names...
	mkdir -p $(DST_DIR)/css
	cat dxr/build/css_manifest | sed 's|css/\([^ ]*\) \([^ ]*\)|$(TMP_DIR)/\1 $(DST_DIR)/\2|' \
	                           | xargs -n2 -I% sh -c 'cp %'
	
	# Copying other static files to hashed names...
	mkdir -p $(DST_DIR)/icons/mimetypes $(DST_DIR)/js/libs $(DST_DIR)/fonts $(DST_DIR)/images
	cat dxr/build/leaf_manifest | sed 's|\([^ ]*\) \([^ ]*\)|$(SRC_DIR)/\1 $(DST_DIR)/\2|' \
	                            | xargs -n2 -I% sh -c 'cp %'
	
	cat dxr/build/leaf_manifest dxr/build/css_manifest > $@

.PHONY: all test clean static_clean static docs dev docker_es shell docker_test docker_clean requirements plugins
