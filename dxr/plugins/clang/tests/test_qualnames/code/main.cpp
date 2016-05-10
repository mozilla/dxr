#include "foo.h"

using namespace bear;
using namespace sonic;

int main() {
  f_class(t_class());
  t_enum_class oversized_feature = t_enum_class::paw;
  f_enum_class(&oversized_feature);
  f_template(t_template<fur>());
  f_typedef(streamOfInts());
  f_bool(true);
}
