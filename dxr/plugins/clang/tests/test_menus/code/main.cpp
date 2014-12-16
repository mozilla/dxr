#include "extern.c"
#include "deeper_folder/deeper.c"

int main(int argc, char* argv[]) {
  numba a = another_file();
  MyClass c;
  deep_thing d;

  Space::foo();
  Bar::foo();

  MACRO;

  return var;
}
