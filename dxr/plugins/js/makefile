build:
	cd analyze_js; npm install

clean:
	rm -rf analyze_js/node_modules

lint: build
	cd analyze_js; node_modules/.bin/eslint .

.PHONY: build clean lint
