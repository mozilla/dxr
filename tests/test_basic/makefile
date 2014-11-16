all:
	# Link paths in dxr.config.in to current working directory
	# replaces PWD with `pwd` and produces dxr.config
	cat dxr.config.in | sed -e 's?PWD?'`pwd`'?g' > dxr.config
	# Navigate into the DXR folder, build using config file
	dxr-build.py
	# Launch test server at port 8000:
	# dxr-serve.py --all target
clean:
	rm -rf dxr.config
	rm -rf temp
	rm -rf target
	cd code; make clean; cd -
