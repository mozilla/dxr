all:
	# Link paths in dxr.config.in to current working directory
	# replaces PWD with `pwd` and produces dxr.config
	cat dxr.config.in | sed -e 's?PWD?'`pwd`'?g' > dxr.config
	# Navigate into the DXR folder, build using config file
	dxr-build.py
	# Launch test server at port 8000:
	# dxr-serve.py target
	# Launch the hg web view at port 8001:
	# cd code; hg serve -p 8001
clean:
	rm -rf dxr.config
	rm -rf temp
	rm -rf target
