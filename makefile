# Things you should consider running:

all: templates plugins

test: all
	python setup.py test

clean:
	rm -rf node_modules/.bin/grunt \
	       node_modules/.bin/nunjucks-precompile \
	       node_modules/grunt* \
	       node_modules/nunjucks \
	       .npm_installed
	find . -name "*.pyc" -exec rm -f {} \;
	$(MAKE) -C dxr/plugins/clang clean

# For deploy script to call:
templates: dxr/static/js/templates.js


# Private things:

plugins:
	$(MAKE) -C dxr/plugins/clang

dxr/static/js/templates.js: dxr/static/templates/nunjucks/*.html \
                            .npm_installed
	node_modules/.bin/nunjucks-precompile dxr/static/templates/nunjucks > dxr/static/js/templates.js

# .npm_installed is an empty file we touch whenever we run npm install. This
# target redoes the install if the packages or lockdown files are newer than
# that file:
.npm_installed: package.json lockdown.json
	npm install
	touch .npm_installed

.PHONY: all test clean plugins templates
