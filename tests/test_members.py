from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class MemberVariableTests(SingleFileTestCase):
    source = """
        class MemberVariable {
            public:
                int member_variable;
        };
        """ + MINIMAL_MAIN

    def test_member_variable(self):
        """Test searching for members of a class (or struct) that contains
        only member variables"""
        self.found_lines_eq('+member:MemberVariable',
            [('class <b>MemberVariable</b> {', 2),
             ('int <b>member_variable</b>;', 4)])


class MemberVariableCtorTests(SingleFileTestCase):
    """Members that do not have an explicit initializer on the constructor
    should not show the constructor as having a reference to that member.
    There's no convenient place in the source to use for the extents for such
    a reference.  Previously we were defaulting to using the location of the
    name of the constructor which would conflict with using that for the
    link for the constructor as well as any other implicitly initialized
    members."""
    source = """
        struct Bar {};
        struct Foo {
            Foo() : baz(0) {}
            Bar bar;
            int baz;
        };
        """ + MINIMAL_MAIN

    def test_implicit_init(self):
        """Test searching for references to a member of a class that is
        implicitly initialized"""
        self.found_nothing('+var-ref:Foo::bar')

    def test_explicit_init(self):
        """Test searching for references to a member of a class that is
        explicitly initialized"""
        self.found_line_eq('+var-ref:Foo::baz', 'Foo() : <b>baz</b>(0) {}')


class MemberFunctionTests(SingleFileTestCase):
    source = """
        class MemberFunction {
            public:
                void member_function();
        };

        void MemberFunction::member_function() {
        }
        """ + MINIMAL_MAIN

    def test_member_function(self):
        """Test searching for members of a class (or struct) that contains
        only member functions"""
        self.found_lines_eq('+member:MemberFunction',
            [(u'class <b>MemberFunction</b> {', 2),
             (u'void MemberFunction::<b>member_function</b>() {', 7)])


class StaticMemberTests(SingleFileTestCase):
    source = """
        class StaticMember {
            public:
                static int static_member;
        };

        int StaticMember::static_member = 0;
        """ + MINIMAL_MAIN

    def test_static_members(self):
        self.found_line_eq('+var:StaticMember::static_member', 'int StaticMember::<b>static_member</b> = 0;')


class MemberTests(SingleFileTestCase):
    # We could probably strip this down a fair bit:
    source = """
        #include <stdint.h>
        #include <string.h>
        #include <assert.h>
        #include <limits.h>

        /** Representation of a BitField, well really, just some annoying part of it */
        class BitField {
            private:
                /** Definition of underlying type for the bitfield*/
                typedef unsigned int _word;

                /** Number of bits per word */
                static const size_t _bitsPerWord = CHAR_BIT * sizeof(_word);

                /** Number of words for size */
                size_t _words() const{
                    return (_size + _bitsPerWord - 1) / _bitsPerWord;
                }

                /** Underlying word array */
                _word* _bits;
                size_t _size;

            public:
                /** Create a new empty bitfield */
                BitField(size_t size){
                    _size = size;
                    _bits = new _word[_words()];
                }

                /** Copy create a bitfield from another */
                BitField(const BitField& bf){
                    _size = bf._size;
                    _bits = new _word[_words()];
                    for(size_t i = 0; i < _words(); i++)
                        _bits[i] = bf._bits[i];
                }

                /** Destructor */
                ~BitField(){
                    if(_bits){
                        delete[] _bits;
                        _bits = NULL;
                    }
                }

                BitField& operator= (const BitField& rhs){
                    for(size_t i = 0; i < _words(); i++)
                        _bits[i] = rhs._bits[i];
                    return *this;
                }

                BitField& operator&= (const BitField& rhs){
                    for(size_t i = 0; i < _words(); i++)
                        _bits[i] &= rhs._bits[i];
                    return *this;
                }
        };

        inline BitField operator&(const BitField& lhs, const BitField& rhs){
            BitField retval(lhs);
            retval &= rhs;
            return retval;
        }
        """ + MINIMAL_MAIN

    def test_members(self):
        """Make sure we can find all the members of a class."""
        self.found_lines_eq('member:BitField',
            [('class <b>BitField</b> {', 8),
             ('size_t <b>_words</b>() const{', 17),
             ('_word* <b>_bits</b>;', 22),
             ('size_t <b>_size</b>;', 23),
             ('<b>BitField</b>(size_t size){', 27),
             ('<b>BitField</b>(const BitField&amp; bf){', 33),
             ('<b>~BitField</b>(){' if self.clang_at_least(3.5) else '<b>~</b>BitField(){', 41),
             ('BitField&amp; <b>operator=</b> (const BitField&amp; rhs){', 48),
             ('BitField&amp; <b>operator&amp;=</b> (const BitField&amp; rhs){', 54)])
