from nose.tools import ok_, eq_, raises

from dxr.testing import DxrInstanceTestCaseMakeFirst

GH_REPO = "https://github.com/someone/somerepo"

# Github remote Https://github.com:
LATEST_G_H_REVISION = "5e2b2b554eb86f90e189217fa9dc2eba66259910"
PREVIOUS_G_H_REVISION = "cb339834998124cb8165aa35ed4635c51b6ac5c2"

# Github remote Ssh://user@github.com:port
LATEST_G_S_REVISION = "f649b19200758ccf0592829abf03b03c4fa2182d"

BB_REPO = "https://bitbucket.org/someone/somerepo"
# Bitbucket remote Git@bitbucket.org:
LATEST_B_G_REVISION = "2d45655982e5267b6c1ee6173aac14be89311947"

class GitTests(DxrInstanceTestCaseMakeFirst):
    """Test our Git integration, both core and omniglot."""
    def test_permalink(self):
        """Make sure the permalink link exists and goes to the right place."""
        response = self.client().get('/code/source/github_https_repo/main.c')
        ok_('/rev/%s/github_https_repo/main.c" title="Permalink" class="permalink icon">Permalink</a>' % LATEST_G_H_REVISION in response.data)
        # Test that it works for this revision and the last one.
        response = self.client().get('/code/rev/%s/github_https_repo/main.c' % LATEST_G_H_REVISION)
        eq_(response.status_code, 200)
        response = self.client().get('/code/rev/%s/github_https_repo/main.c' % PREVIOUS_G_H_REVISION)
        eq_(response.status_code, 200)

    def test_deep_permalink(self):
        """Make sure the permalink link exists and goes to the right place for files not in the
        top-level directory. This test makes sure that the permalink works even for files not in
        the top level git root directory, since `git show` will resolve paths relative to the git
        root rather than the current working directory unless we specify ./ before the path."""

        response = self.client().get('/code/source/github_https_repo/deeper/deeper_file')
        ok_('/rev/%s/github_https_repo/deeper/deeper_file" title="Permalink" class="permalink icon">Permalink</a>' % LATEST_G_H_REVISION in response.data)
        response = self.client().get('/code/rev/%s/github_https_repo/deeper/deeper_file' % LATEST_G_H_REVISION)
        eq_(response.status_code, 200)
        ok_("This file tests" in response.data)

    def test_pygmentize(self):
        """Check that the pygmentize FileToSkim correctly colors a file from permalink."""
        client = self.client()
        response = client.get('/code/rev/%s/github_https_repo/main.c' % PREVIOUS_G_H_REVISION)
        ok_('<span class="c">// Hello World Example\n</span>' in response.data)
        # Query it again to test that the Vcs cache functions.
        response = client.get('/code/rev/%s/github_https_repo/main.c' % PREVIOUS_G_H_REVISION)
        ok_('<span class="c">// Hello World Example\n</span>' in response.data)

    @raises(AssertionError) # remove this line when fixed
    def test_untracked_file(self):
        """Check that the sidebar displays "Untracked file" if and only if a
        file is untracked."""
        response = self.client().get('/code/source/untracked_file')
        ok_('<h4>Untracked file</h4>' in response.data)
        response = self.client().get('/code/source/github_https_repo/main.c')
        ok_('<h4>Untracked file</h4>' not in response.data)

    def test_vcs_links_display(self):
        """Check that the "VCS Links" options appear if and only if we're able
        to find a suitable remote for a file in a VCS repository."""
        response = self.client().get('/code/source/github_https_repo/main.c')
        ok_('<h4>VCS Links</h4>' in response.data)
        # no_remote/README is tracked, but its repo has no remote.
        response = self.client().get('/code/source/no_remote/README')
        ok_('<h4>VCS Links</h4>' not in response.data)

    #### Github "origin" remote https://github.com/someone/somerepo.git
    def test_github_https_diff(self):
        """Make sure the github diff link exists and goes to the right place."""
        response = self.client().get('/code/source/github_https_repo/main.c')
        ok_('%s/commit/%s" title="Diff" class="diff icon">Diff</a>' % (GH_REPO, LATEST_G_H_REVISION) in response.data)

    def test_github_https_blame(self):
        """Make sure the github blame link exists and goes to the right place."""
        response = self.client().get('/code/source/github_https_repo/main.c')
        ok_('%s/blame/%s/main.c" title="Blame" class="blame icon">Blame</a>' % (GH_REPO, LATEST_G_H_REVISION) in response.data)

    def test_github_https_raw(self):
        """Make sure the github raw link exists and goes to the right place."""
        response = self.client().get('/code/source/github_https_repo/main.c')
        ok_('%s/raw/%s/main.c" title="Raw" class="raw icon">Raw</a>' % (GH_REPO, LATEST_G_H_REVISION) in response.data)

    def test_github_https_log(self):
        """Make sure the github log link exists and goes to the right place."""
        response = self.client().get('/code/source/github_https_repo/main.c')
        ok_('%s/commits/%s/main.c" title="Log" class="log icon">Log</a>' % (GH_REPO, LATEST_G_H_REVISION) in response.data)

    #### Github "origin" remote ssh://user@github.com:1111/someone/somerepo.git
    def test_repo_root_outside_code(self):
        """Make sure we find a repo even when its root is outside our tree root."""
        response = self.client().get('/code/source/in_repo_outside_code')
        ok_('https://github.com:1111/someone/somerepo/commits/%s/code/in_repo_outside_code" title="Log" class="log icon">Log</a>' % LATEST_G_S_REVISION in response.data)

    #### Bitbucket "origin" remote git@bitbucket.org:someone/somerepo.git
    def test_bitbucket_gitssh_diff(self):
        """Make sure the bitbucket diff link exists and goes to the right place."""
        response = self.client().get('/code/source/bitbucket_gitssh_repo/README')
        ok_('%s/diff/README?diff2=%s" title="Diff" class="diff icon">Diff</a>' % (BB_REPO, LATEST_B_G_REVISION) in response.data)

    def test_bitbucket_gitssh_blame(self):
        """Make sure the bitbucket blame link exists and goes to the right place."""
        response = self.client().get('/code/source/bitbucket_gitssh_repo/README')
        ok_('%s/annotate/%s/README" title="Blame" class="blame icon">Blame</a>' % (BB_REPO, LATEST_B_G_REVISION) in response.data)

    def test_bitbucket_gitssh_raw(self):
        """Make sure the bitbucket raw link exists and goes to the right place."""
        response = self.client().get('/code/source/bitbucket_gitssh_repo/README')
        ok_('%s/raw/%s/README" title="Raw" class="raw icon">Raw</a>' % (BB_REPO, LATEST_B_G_REVISION) in response.data)

    def test_bitbucket_gitssh_log(self):
        """Make sure the bitbucket log link exists and goes to the right place."""
        response = self.client().get('/code/source/bitbucket_gitssh_repo/README')
        ok_('%s/history-node/%s/README" title="Log" class="log icon">Log</a>' % (BB_REPO, LATEST_B_G_REVISION) in response.data)

    #### There's also the repo code/no_remote which has no remote - if we don't
    #### assert during indexing then we pass.
