from os.path import dirname, join
from shutil import copyfile

from dxr.testing import DxrInstanceTestCase

from nose import SkipTest
from nose.tools import ok_


class MercurialTests(DxrInstanceTestCase):
    """Tests that the diff links for files go somewhere helpful"""

    @classmethod
    def teardown_class(cls):
        """hg changes its dirstate file during the tests. Restore it so git
        doesn't flag it as a change.

        We can't just gitignore it, as git declines to ignore committed files.

        """
        super(cls, MercurialTests).teardown_class()
        this_dir = dirname(__file__)
        copyfile(join(this_dir, 'hg_dirstate_backup'),
                 join(this_dir, 'code', '.hg', 'dirstate'))

    def test_diff_file1(self):
        """Make sure the diff link goes to the first after-initial commit."""
        response = self.client().get('/code/source/ChangedInCommit1')
        ok_('/diff/2e86c4e11a82/ChangedInCommit1" title="Diff" class="diff icon">Diff</a>' in response.data)

    def test_diff_file2(self):
        """Make sure the diff link goes to the second after-initial commit."""
        response = self.client().get('/code/source/ChangedInCommit2')
        ok_('/diff/cd18424a4dab/ChangedInCommit2" title="Diff" class="diff icon">Diff</a>' in response.data)

    def test_diff_file3(self):
        """Make sure the diff link goes to the third after-initial commit."""
        response = self.client().get('/code/source/Filename With Space')
        ok_('/diff/1be3fc90ef01/Filename With Space" title="Diff" class="diff icon">Diff</a>' in response.data)

    def test_blame(self):
        """Make sure the diff link goes to the first after-initial commit."""
        response = self.client().get('/code/source/ChangedInCommit1')
        ok_('/annotate/1be3fc90ef01/ChangedInCommit1" title="Blame" class="blame icon">Blame</a>' in response.data)

    def test_raw(self):
        """Make sure the diff link goes to the second after-initial commit."""
        response = self.client().get('/code/source/ChangedInCommit2')
        ok_('/raw-file/1be3fc90ef01/ChangedInCommit2" title="Raw" class="raw icon">Raw</a>' in response.data)

    def test_log(self):
        """Make sure the diff link goes to the third after-initial commit."""
        response = self.client().get('/code/source/Filename With Space')
        ok_('/filelog/1be3fc90ef01/Filename With Space" title="Log" class="log icon">Log</a>' in response.data)

    def test_permalink(self):
        """Make sure the diff link goes to the third after-initial commit."""
        # Flask's url_for will escape the url, so spaces become %20
        response = self.client().get('/code/source/Filename With Space')
        ok_('/rev/1be3fc90ef01/Filename%20With%20Space" title="Permalink" class="permalink icon">Permalink</a>' in response.data)
