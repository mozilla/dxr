// The namespace and translation unit setups of this tree provide some of the
// conditions under which clang used to give different parameter type names
// depending on where in the source tree the parameter was requested.

namespace bear {

class t_class {};
enum class t_enum_class { paw };

} // namespace bear

template<class T> class t_template { };
typedef t_template<int> streamOfInts;

// "Find callers" on these function decls used to return 0 results.
void f_class(bear::t_class );
void f_enum_class(const bear::t_enum_class * const );
namespace sonic {
void f_typedef(streamOfInts ); // (This one has always worked.)
class fur {};
} // namespace sonic
void f_template(t_template<sonic::fur> );
void f_bool(bool );
