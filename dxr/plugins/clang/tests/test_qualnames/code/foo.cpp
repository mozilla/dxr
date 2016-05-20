#include "foo.h"

using namespace bear;
using namespace sonic;

// "Find callers" on these functions used to return 0 results.
void f_class(t_class ) {}
void f_enum_class(const t_enum_class * const ) {}
void f_template(t_template<fur> ) {}
void sonic::f_typedef(streamOfInts ) {} // (This one has always worked.)
void f_bool(bool ) {}
