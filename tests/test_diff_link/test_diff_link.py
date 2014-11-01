from dxr.testing import DxrInstanceTestCase
from nose.tools import ok_

class DiffLinkTests(DxrInstanceTestCase):
    """Tests that the diff links for files go somewhere helpful"""
    def test_diff_file1(self):
        '''
        Make sure the diff link goes to the first after-initial commit.
        '''
        response = self.client().get('/code/source/ChangedInCommit1')
        ok_('/diff/2e86c4e11a82/ChangedInCommit1" title="Diff" class="diff icon">Diff</a>' in response.data)

    def test_diff_file2(self):
        '''
        Make sure the diff link goes to the second after-initial commit.
        '''
        response = self.client().get('/code/source/ChangedInCommit2')
        ok_('diff/cd18424a4dab/ChangedInCommit2" title="Diff" class="diff icon">Diff</a>' in response.data)
