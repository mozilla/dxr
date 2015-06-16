from dxr.testing import SingleFileTestCase


class FilterAggregateTests(SingleFileTestCase):
    """Tests the id- and ref- aggregate filters defined in query.py"""
    source = r"""#include <stdio.h>

                 int foo(int n) {
                     return n - 2;
                 }

                 // Hello World Example
                 int main(int argc, char* argv[]){
                     int a_number = 2;
                     a_number++;
                     printf("Hello World %d\n", foo(a_number));
                     return 0;
                }
            """

    def test_id(self):
        """Test that id-filter works correctly."""
        self.found_line_eq(
            'id:foo',
            'int <b>foo</b>(int n) {',
            3)
        self.found_line_eq(
            'id:main',
            'int <b>main</b>(int argc, char* argv[]){',
            8)
        self.found_line_eq(
            'id:a_number',
            'int <b>a_number</b> = 2;',
            9)

    def test_ref(self):
        """Test that ref-filter works correctly."""
        self.found_lines_eq(
            'ref:a_number',
            [('<b>a_number</b>++;', 10),
             ('printf("Hello World %d\\n", foo(<b>a_number</b>));', 11)
             ])
        self.found_line_eq(
            'ref:foo',
            'printf("Hello World %d\\n", <b>foo(a_number)</b>);',
            11)
