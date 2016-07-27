"""Test that the plugin finds the expected descriptions, and they appear on the
browse pages.

"""
from nose.tools import ok_

from dxr.testing import DxrInstanceTestCase


class DescriptionTests(DxrInstanceTestCase):
    def test_browse_page(self):
        """Test that the expected descriptions appear on the root page.

        """
        response = self.client().get('/code/source/').data
        ok_("Highly important subfolder. with a description over 100 bbytesbytesbytesbytesbytesbytesbytesbytesbyt" in response)
        # Make sure we didn't exceed the limit.
        ok_("Highly important subfolder. with a description over 100 bbytesbytesbytesbytesbytesbytesbytesbytesbyte" not in response)
        ok_("A line of the readme, with prepended spaces." in response)
        # Check that I stripped prepended spaces.
        ok_("  A line of the readme, with prepended spaces." not in response)
        # Javascript description with /** */ comment
        ok_("Define foon, a dynamic, higher-order, weakly typed, late-bound function/method." in response)
        # Python docstring
        ok_("foo.py: some very Pythonic codes." in response)
        # First case of generic description_re.
        ok_("more foo" in response)
        # Second case of generic description_re.
        ok_("great code" in response)
        # Make sure license, vim, emacs mode lines skip.
        ok_("The description appears after a MPL and after some mode settings." in response)
        # Test that the comment regular expression won't time out from lazy
        # searching on big strings.
        ok_("hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh" in response)

    def test_sub_browse_page(self):
        """Test that the expected descriptions appear on the subfolder's page.

        """
        response = self.client().get('/code/source/sub/').data
        # cpp description with /* */ comment
        ok_("Foo is great." in response)
        # html title
        ok_("foo html!" in response)
        # readme line
        ok_("Highly important subfolder. with a description over 100 bbytesbytesbytesbytesbytesbytesbytesbytesbyt" in response)
