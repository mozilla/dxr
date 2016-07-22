build: .npm_installed
	cd analyze_js && npm install

# Remove anything within node_modules that's not checked into git. Skip things
# with spaces in them, lest xargs screw up and delete the wrong thing.
clean:
	rm -f .npm_installed
	cd analyze_js/node_modules && git ls-files -o --directory -x '* *' -x '.DS_Store' | xargs rm -rf

lint: build
	cd analyze_js && node_modules/.bin/eslint .

# .npm_installed is an empty file we touch whenever we run npm install. This
# target redoes the install if the packages or lockdown files are newer than
# that file:
.npm_installed: analyze_js/package.json analyze_js/lockdown.json
	cd analyze_js && npm install
	touch $@

.PHONY: build clean lint
