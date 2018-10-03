from nose.tools import ok_, eq_

from dxr.testing import DxrInstanceTestCaseMakeFirst

LATEST_REVISION = "4"
INITIAL_FILE = "Initial.txt"
CHANGED_FILE = "Changed.txt"
DIRECTORY = "ExampleDirectory"
DEEP_FILE_NAME = "FileInDirectory.txt"
DEEP_FILE_PATH = DIRECTORY + "/" + DEEP_FILE_NAME

class SubversionTests(DxrInstanceTestCaseMakeFirst):
    """Test our Subversion integration, both core and omniglot."""

    def test_initial_file(self):
        """Check the initial file in the root folder."""
        response = self.client().get('/code/source/' + INITIAL_FILE)
        eq_(response.status_code, 200)
        ok_('Subversion (r1)' in response.data)

    def test_directory(self):
        """Check the directory view."""
        response = self.client().get('/code/source/' + DIRECTORY)
        eq_(response.status_code, 200)
        ok_('<a href="/code/source/' + DEEP_FILE_PATH + '" class="icon txt">' + DEEP_FILE_NAME + '</a>' in response.data)

    def test_deep_file(self):
        """Check the file in the directory."""
        response = self.client().get('/code/source/' + DEEP_FILE_PATH)
        eq_(response.status_code, 200)
        ok_('Subversion (r4)' in response.data)

    def test_raw_exists(self):
        """Make sure the raw link exists."""
        response = self.client().get('/code/source/' + INITIAL_FILE )
        eq_(response.status_code, 200)
        ok_('/code/repo/' + INITIAL_FILE + '" title="Raw" class="raw icon">Raw</a>' in response.data)

    def test_permalink_exists(self):
        """Make sure the permalink exists."""
        source_url = '/code/source/' + CHANGED_FILE
        response = self.client().get(source_url)
        eq_(response.status_code, 200)
        ok_('/rev/' + LATEST_REVISION + '/' + CHANGED_FILE + '" title="Permalink" class="permalink icon">Permalink</a>' in response.data)

    def test_permalink_works_latest(self):
        """Check the permalink of the latest repository revision."""
        perma_url = '/code/rev/' + LATEST_REVISION + '/' + CHANGED_FILE
        response = self.client().get(perma_url)
        eq_(response.status_code, 200)

    def test_permalink_works_last(self):
        """Ccheck the permalink of the latest file revision."""
        perma_url = '/code/rev/3/' + CHANGED_FILE
        response = self.client().get(perma_url)
        eq_(response.status_code, 200)
        ok_('Mozilla!' in response.data)

    def test_permalink_works_first(self):
        """Check the permalink of the first file revision."""
        perma_url = '/code/rev/2/' + CHANGED_FILE
        response = self.client().get(perma_url)
        eq_(response.status_code, 200)
        ok_('Mozilla?' in response.data)

    def test_untracked_makefile(self):
        response = self.client().get('/code/source/Makefile')
        ok_('<h4>Untracked file</h4>' in response.data)

    def test_untracked_tar(self):
        response = self.client().get('/code/source/repo.tar')
        ok_('<h4>Untracked file</h4>' in response.data)
