from os.path import dirname, join
from shutil import copyfile

from dxr.testing import DxrInstanceTestCase

from nose import SkipTest
from nose.tools import ok_


class GitTests(DxrInstanceTestCase):
    """Tests that the diff links for files go somewhere helpful"""

    def test_diff(self):
        """Make sure the diff link goes to the first after-initial commit."""
        response = self.client().get('/code/source/main.c')
        ok_('/commit/cb339834998124cb8165aa35ed4635c51b6ac5c2" title="Diff" class="diff icon">Diff</a>' in response.data)

    def test_blame(self):
        """Make sure the diff link goes to the first after-initial commit."""
        response = self.client().get('/code/source/main.c')
        ok_('/blame/cb339834998124cb8165aa35ed4635c51b6ac5c2/main.c" title="Blame" class="blame icon">Blame</a>' in response.data)

    def test_raw(self):
        """Make sure the diff link goes to the second after-initial commit."""
        response = self.client().get('/code/source/main.c')
        ok_('/raw/cb339834998124cb8165aa35ed4635c51b6ac5c2/main.c" title="Raw" class="raw icon">Raw</a>' in response.data)

    def test_log(self):
        """Make sure the diff link goes to the third after-initial commit."""
        response = self.client().get('/code/source/main.c')
        ok_('/commits/cb339834998124cb8165aa35ed4635c51b6ac5c2/main.c" title="Log" class="log icon">Log</a>' in response.data)

    def test_permalink(self):
        """Make sure the diff link goes to the third after-initial commit."""
        # Flask's url_for will escape the url, so spaces become %20
        response = self.client().get('/code/source/main.c')
        ok_('/rev/cb339834998124cb8165aa35ed4635c51b6ac5c2/main.c" title="Permalink" class="permalink icon">Permalink</a>' in response.data)

    def test_pygmentize(self):
        # Check that the pygmentize FileToSkim correctly colors a file from permalink
        response = self.client().get('/code/rev/cb339834998124cb8165aa35ed4635c51b6ac5c2/main.c')
        ok_('<span class="c">// Hello World Example</span>' in response.data)