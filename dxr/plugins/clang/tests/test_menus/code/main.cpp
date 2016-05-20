#include "extern.c"
#include "deeper_folder/deeper.c"
#include "../very_extern.h"

int main(int argc, char* argv[]) {
  numba a = another_file();
  MyClass c;
  deep_thing d;

  Space::foo();
  Bar::foo();

  MACRO;

  var++;

  BaseClass* der = new DerivedClass;
  der->virtualFunc();
  delete der;

  Z zz;
  zz.~Z();

  return 1;
}

VERY_EXTERNAL
