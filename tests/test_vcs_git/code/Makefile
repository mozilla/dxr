REPOS=$(wildcard */)

all:
	@$(foreach REPO, $(REPOS), cd $(REPO) && tar -xf git.tar && cd ..;)
	@cd ../ && tar -xf git.tar
	@touch untracked_file

clean:
	@$(foreach REPO, $(REPOS), cd $(REPO) && rm -rf .git && cd ..;)
	@cd ../ && rm -rf .git
	@rm untracked_file
