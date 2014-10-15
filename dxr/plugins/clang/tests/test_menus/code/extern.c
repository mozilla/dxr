// We define most things in this file and reference them in main.cpp. That
// way, menu_on(), which favors the first instance of a menu-having string in
// a file, is targetable to either definitions or refs.

typedef int numba;

numba another_file() {
  return 5;
}

int var = 5;

class MyClass;
class MyClass
{
};

namespace Space {
  void foo() {}
}
namespace Bar = Space;
