from os.path import dirname, join
import subprocess

from dxr.testing import DxrInstanceTestCaseMakeFirst

from nose import SkipTest
from nose.tools import ok_

# Hgweb remote http://33.33.33.77:8001
H_REPO = 'http://33.33.33.77:8001'
SECOND_H_REVISION = '2e86c4e11a82f3ec17867468e499e85ec3cbf441'
THIRD_H_REVISION = 'cd18424a4dab95361e25e86398e557d3d889e2c8'
FOURTH_H_REVISION = '1be3fc90ef0104cf186fac7bc0bbfea17ba6ebdc'
FIFTH_H_REVISION = '84798105c9ab5897f8c7d630d133d9003b44a62f'

# Bitbucket remote ssh://user@bitbucket.org
BS_REPO = 'https://bitbucket.org/someone/somerepo'
FIRST_BS_REVISION = 'a7eb0f0153637af80073fc3c395524fb734fa535'


class MercurialTests(DxrInstanceTestCaseMakeFirst):
    """Test our Mercurial integration, both core and omniglot."""
    def test_permalink(self):
        """Make sure the permalink exists, and that the response is ok."""
        # Flask's url_for will escape the url, so spaces become %20
        response = self.client().get('/code/source/ip_addr_repo/Colon: name')
        ok_('/rev/%s/ip_addr_repo/Colon:%%20name" title="Permalink" class="permalink icon">Permalink</a>' % FIFTH_H_REVISION in response.data)
        response = self.client().get('/code/rev/%s/Colon: name' % FIFTH_H_REVISION)
        ok_(response.status_code, 200)

    #### Hgweb 'default' remote http://33.33.33.77:8001 :
    def test_hgweb_diff_file1(self):
        """Make sure the diff link goes to the first after-initial commit."""
        response = self.client().get('/code/source/ip_addr_repo/ChangedInCommit1')
        ok_('%s/diff/%s/ChangedInCommit1" title="Diff" class="diff icon">Diff</a>' % (H_REPO, SECOND_H_REVISION) in response.data)

    def test_hgweb_diff_file2(self):
        """Make sure the diff link goes to the second after-initial commit."""
        response = self.client().get('/code/source/ip_addr_repo/ChangedInCommit2')
        ok_('%s/diff/%s/ChangedInCommit2" title="Diff" class="diff icon">Diff</a>' % (H_REPO, THIRD_H_REVISION) in response.data)

    def test_hgweb_diff_file3(self):
        """Make sure the diff link goes to the third after-initial commit."""
        response = self.client().get('/code/source/ip_addr_repo/Filename With Space')
        ok_('%s/diff/%s/Filename With Space" title="Diff" class="diff icon">Diff</a>' % (H_REPO, FOURTH_H_REVISION) in response.data)

    def test_hgweb_blame(self):
        """Make sure the blame link goes to the right place."""
        response = self.client().get('/code/source/ip_addr_repo/ChangedInCommit1')
        ok_('%s/annotate/%s/ChangedInCommit1" title="Blame" class="blame icon">Blame</a>' % (H_REPO, FIFTH_H_REVISION) in response.data)

    def test_hgweb_raw(self):
        """Make sure the raw link goes to the right place."""
        response = self.client().get('/code/source/ip_addr_repo/ChangedInCommit2')
        ok_('%s/raw-file/%s/ChangedInCommit2" title="Raw" class="raw icon">Raw</a>' % (H_REPO, FIFTH_H_REVISION) in response.data)

    def test_hgweb_log(self):
        """Make sure the log link goes to the right place."""
        response = self.client().get('/code/source/ip_addr_repo/Filename With Space')
        ok_('%s/filelog/%s/Filename With Space" title="Log" class="log icon">Log</a>' % (H_REPO, FIFTH_H_REVISION) in response.data)

    #### Bitbucket 'default' remote ssh://user@bitbucket.org/someone/somerepo
    def test_bitbucket_diff(self):
        """Make sure the diff link goes to the one and only commit."""
        response = self.client().get('/code/source/bitbucket_repo/README')
        # Bitbucket looks up an implicit diff1 in which the file at rev diff2
        # last changed, so our rev should just be the current rev.
        ok_('%s/diff/README?diff2=%s" title="Diff" class="diff icon">Diff</a>' % (BS_REPO, FIRST_BS_REVISION) in response.data)

    def test_bitbucket_blame(self):
        """Make sure the blame link goes to the right place."""
        response = self.client().get('/code/source/bitbucket_repo/README')
        ok_('%s/annotate/%s/README" title="Blame" class="blame icon">Blame</a>' % (BS_REPO, FIRST_BS_REVISION) in response.data)

    def test_bitbucket_raw(self):
        """Make sure the raw link goes to the right place."""
        response = self.client().get('/code/source/bitbucket_repo/README')
        ok_('%s/raw/%s/README" title="Raw" class="raw icon">Raw</a>' % (BS_REPO, FIRST_BS_REVISION) in response.data)

    def test_bitbucket_log(self):
        """Make sure the log link goes to the right place."""
        response = self.client().get('/code/source/bitbucket_repo/README')
        ok_('%s/history-node/%s/README" title="Log" class="log icon">Log</a>' % (BS_REPO, FIRST_BS_REVISION) in response.data)

    #### There's also the repo code/no_default with no 'default' remote - if we
    #### don't assert during indexing then we pass.
