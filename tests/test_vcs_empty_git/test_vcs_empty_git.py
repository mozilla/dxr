from dxr.testing import DxrInstanceTestCaseMakeFirst


class EmptyGitTests(DxrInstanceTestCaseMakeFirst):
    def test_empty_repo(self):
        """By running indexing over an empty git repo, provoke ``git rev-parse
        HEAD`` into returning an error status code, and make sure we deal with
        it properly--by not crashing."""
