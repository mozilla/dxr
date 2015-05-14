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

  return var;
}

VERY_EXTERNAL