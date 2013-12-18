from dxr.testing import DxrInstanceTestCase

from nose.tools import eq_


class ParallelControllerTests(DxrInstanceTestCase):
    """Tests for the /parallel/ controller"""

    def test_existent_parallel_file(self):
        """Make sure the /parallel controller redirects to an existent parallel
        file."""
        response = self.client().get('/code/parallel/folder/nested_folder/hai')
        eq_(response.headers['Location'],
            'http://localhost/code/source/folder/nested_folder/hai')

    def test_existent_parallel_folder(self):
        """Make sure the /parallel controller redirects to an existent parallel
        folder."""
        response = self.client().get('/code/parallel/folder/')
        eq_(response.headers['Location'],
            'http://localhost/code/source/folder/')

    def test_nonexistent_parallel(self):
        """Make sure the /parallel controller redirects to an existent parallel
        file or folder."""
        response = self.client().get('/code/parallel/folder/nope')
        eq_(response.headers['Location'], 'http://localhost/code/source/')
