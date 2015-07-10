from nose.tools import ok_, eq_

from dxr.testing import DxrInstanceTestCaseMakeFirst

LATEST_REVISION = "5e2b2b554eb86f90e189217fa9dc2eba66259910"
PREVIOUS_REVISION = "cb339834998124cb8165aa35ed4635c51b6ac5c2"

class GitTests(DxrInstanceTestCaseMakeFirst):
    """Test our Git integration, both core and omniglot."""

    def test_diff(self):
        """Make sure the diff link exists and goes to the right place."""
        response = self.client().get('/code/source/main.c')
        ok_('/commit/%s" title="Diff" class="diff icon">Diff</a>' % LATEST_REVISION in response.data)

    def test_blame(self):
        """Make sure the blame link exists and goes to the right place."""
        response = self.client().get('/code/source/main.c')
        ok_('/blame/%s/main.c" title="Blame" class="blame icon">Blame</a>' % LATEST_REVISION in response.data)

    def test_raw(self):
        """Make sure the raw link exists and goes to the right place."""
        response = self.client().get('/code/source/main.c')
        ok_('/raw/%s/main.c" title="Raw" class="raw icon">Raw</a>' % LATEST_REVISION in response.data)

    def test_log(self):
        """Make sure the log link exists and goes to the right place."""
        response = self.client().get('/code/source/main.c')
        ok_('/commits/%s/main.c" title="Log" class="log icon">Log</a>' % LATEST_REVISION in response.data)

    def test_permalink(self):
        """Make sure the permalink link exists and goes to the right place."""
        response = self.client().get('/code/source/main.c')
        ok_('/rev/%s/main.c" title="Permalink" class="permalink icon">Permalink</a>' % LATEST_REVISION in response.data)
        # Test that it works for this revision and the last one.
        response = self.client().get('/code/rev/%s/main.c' % LATEST_REVISION)
        eq_(response.status_code, 200)
        response = self.client().get('/code/rev/%s/main.c' % PREVIOUS_REVISION)
        eq_(response.status_code, 200)

    def test_deep_permalink(self):
        """Make sure the permalink link exists and goes to the right place for files not in the
        top-level directory. This test makes sure that the permalink works even for files not in
        the top level git root directory, since `git show` will resolve paths relative to the git
        root rather than the current working directory unless we specify ./ before the path."""

        response = self.client().get('/code/source/deeper/deeper_file')
        ok_('/rev/%s/deeper/deeper_file" title="Permalink" class="permalink icon">Permalink</a>' % LATEST_REVISION in response.data)
        response = self.client().get('/code/rev/%s/deeper/deeper_file' % LATEST_REVISION)
        eq_(response.status_code, 200)
        ok_("This file tests" in response.data)

    def test_pygmentize(self):
        """Check that the pygmentize FileToSkim correctly colors a file from permalink."""
        client = self.client()
        response = client.get('/code/rev/%s/main.c' % PREVIOUS_REVISION)
        ok_('<span class="c">// Hello World Example\n</span>' in response.data)
        # Query it again to test that the Vcs cache functions.
        response = client.get('/code/rev/%s/main.c' % PREVIOUS_REVISION)
        ok_('<span class="c">// Hello World Example\n</span>' in response.data)
