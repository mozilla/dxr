import json

from nose.tools import eq_

from dxr.testing import SingleFileTestCase


class ContextTests(SingleFileTestCase):
    """Tests the id- and ref- aggregate filters defined in query.py"""
    source = r"""#include <stdio.h>
// Hello World Example
int main(int argc, char* argv[]){
    printf("Hello World %d\n", 2);
    return 0;
}
            """

    def get_ctx(self, fr, to):
        """Helper method to get lines from fr to to.
        """
        return json.loads(self.client().get(
            self.url_for('.lines', tree='code', path='main', start=fr, end=to))
            .data)['lines']

    def test_normal(self):
        """Test that normal context getting works."""
        eq_(self.get_ctx(1, 2),
            [{'line_number': 1, 'line': '#include <stdio.h>\n'},
             {'line_number': 2, 'line': '// Hello World Example\n'}])
        eq_(self.get_ctx(2, 5),
            [{u'line_number': 2, u'line': u'// Hello World Example\n'},
             {u'line_number': 3, u'line': u'int main(int argc, char* argv[]){\n'},
             {u'line_number': 4, u'line': u'    printf("Hello World %d\\n", 2);\n'},
             {u'line_number': 5, u'line': u'    return 0;\n'}])

    def test_edges(self):
        """Test that the edge cases of context getting don't crash."""
        eq_(self.get_ctx(0, 3),
            [{u'line_number': 1, u'line': u'#include <stdio.h>\n'},
             {u'line_number': 2, u'line': u'// Hello World Example\n'},
             {u'line_number': 3, u'line': u'int main(int argc, char* argv[]){\n'}])
        eq_(self.get_ctx(3, 9),
            [{u'line_number': 3, u'line': u'int main(int argc, char* argv[]){\n'},
             {u'line_number': 4, u'line': u'    printf("Hello World %d\\n", 2);\n'},
             {u'line_number': 5, u'line': u'    return 0;\n'},
             {u'line_number': 6, u'line': u'}\n'},
             {u'line_number': 7, u'line': u'            '}])
