"""esprima things the newfangled Unicode line- and paragraph-break chars should
constitute line breaks for the purpose of reported token positions. DXR is not
so gullible.

"""
from dxr.testing import DxrInstanceTestCase


class LineBreakTests(DxrInstanceTestCase):
    def test_devilry(self):
        """Make sure the Unicode devilry is not considered to break lines for
        the purpose of token position reporting.

        If we mess up and treat the unicode devilry as line breaks, we'll
        get an IndexError and *certainly* not the right answer.

        """
        self.found_lines_eq('ref:foo', [('<b>foo</b>();', 5),
                                        ('<b>foo</b>();', 8),
                                        ('<b>foo</b>();', 11)])
