all:
	# Link paths in dxr.config.in to current working directory
	# replaces PWD with `pwd` and produces dxr.config
	cat dxr.config.in | sed -e 's?PWD?'`pwd`'?g' > dxr.config
	# Navigate into the DXR folder, build using config file
	dxr-build.py
	# Launch the hg web view
	cd code; hg serve -p 8001 --pid-file ../hgserve.pid > /dev/null 2>/dev/null &
	# Launch test server at port 8000:
	# dxr-serve.py target
clean:
	rm -rf dxr.config
	rm -rf temp
	rm -rf target
	if [ -f hgserve.pid ]; then cat hgserve.pid | xargs kill; fi;
	rm -f hgserve.pid
