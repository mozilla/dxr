all:
	@tar -xf repo.tar
	@svn checkout file://`pwd`/repo .

clean:
	@rm -f Initial.txt
	@rm -f Changed.txt
	@rm -rf ExampleDirectory
	@rm -rf .svn
	@rm -rf repo
