# Things you should consider running:

all: static plugins

test: all
	python setup.py test

clean: static_clean
	rm -rf node_modules/.bin/nunjucks-precompile \
	       node_modules/nunjucks \
	       .npm_installed
	find . -name "*.pyc" -exec rm -f {} \;
	$(MAKE) -C dxr/plugins/clang clean

static_clean:
	rm -rf dxr/static_unhashed/js/templates.js \
	       dxr/build \
	       dxr/static \
	       dxr/static_manifest

# Cache-bust static assets:
static: dxr/static_unhashed/js/templates.js \
	    dxr/static_manifest


# Private things:

# Just to make the old deploy script happy:
templates: static

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

# Static-file cachebusting:

SRC_DIR := dxr/static_unhashed
DST_DIR := dxr/static
TMP_DIR := dxr/build
# The URL prefix through which static assets will be fetched in production:
URL := /static
# Static files that don't refer to any others:
LEAVES := $(shell find $(SRC_DIR) -type f ! -name '.DS_Store' ! -name '*.css')
# CSS files do refer to other static files, via url(...):
CSS := $(shell find $(SRC_DIR) -type f -name '*.css')
CSS_TEMPS := $(addprefix $(TMP_DIR)/,$(notdir $(shell find $(SRC_DIR)/css -name '*.css')))

# We kick out lines like "abcde12345 somefile.ext", then pass those args, in
# pairs, to sed, to construct the manifest lines, which look like
# "fonts/icons.eot fonts/icons.383e693f.eot".
dxr/build/leaf_manifest: $(LEAVES)
	# Building leaf-asset submanifest...
	mkdir -p $(@D)
	echo $(LEAVES) | xargs -n1 -I% sh -c 'md5sum %' \
	               | xargs -n2 \
	               | sed 's|\(........\)[a-f0-9]* $(SRC_DIR)/\([^.]*\)\.\(.*\)|$(URL)/\2.\3 $(URL)/\2.\1.\3|' \
	               > $@

# Copy the CSS files to build/*.css and substitute their references.
# See https://www.gnu.org/software/make/manual/html_node/Static-Usage.html
$(CSS_TEMPS): $(TMP_DIR)/%.css: $(SRC_DIR)/css/%.css dxr/build/leaf_manifest
	./replace_urls.py dxr/build/leaf_manifest $< > $@

dxr/build/css_manifest: $(CSS_TEMPS)
	# Building CSS submanifest...
	echo $(CSS_TEMPS) | xargs -n1 -I% sh -c 'md5sum %' \
	                  | xargs -n2 \
	                  | sed 's|\(........\)[a-f0-9]* $(TMP_DIR)/\([^.]*\)\.\(.*\)|$(URL)/css/\2.\3 $(URL)/css/\2.\1.\3|' \
	                  > $@

# Add CSS hashes to those already in leaf_manifest:
dxr/static_manifest: $(CSS_TEMPS) dxr/build/leaf_manifest dxr/build/css_manifest
	# Copying CSS files to hashed names...
	mkdir -p $(DST_DIR)/css
	cat dxr/build/css_manifest | sed 's|$(URL)/css\([^ ]*\) $(URL)\([^ ]*\)|$(TMP_DIR)\1 $(DST_DIR)\2|' \
	                           | xargs -n2 -I% sh -c 'cp %'
	
	# Copying other static files to hashed names...
	mkdir -p $(DST_DIR)/icons/mimetypes $(DST_DIR)/js/libs $(DST_DIR)/fonts $(DST_DIR)/images
	cat dxr/build/leaf_manifest | sed 's|$(URL)\([^ ]*\) $(URL)\([^ ]*\)|$(SRC_DIR)\1 $(DST_DIR)\2|' \
	                            | xargs -n2 -I% sh -c 'cp %'
	
	cat dxr/build/leaf_manifest dxr/build/css_manifest > $@

.PHONY: all test clean static_clean static templates plugins
