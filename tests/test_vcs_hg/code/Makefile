REPOS=$(wildcard */)

all:
	@$(foreach REPO, $(REPOS), cd $(REPO) && tar -xf hg.tar && cd ..;)

clean:
	@$(foreach REPO, $(REPOS), cd $(REPO) && rm -rf .hg && cd ..;)
