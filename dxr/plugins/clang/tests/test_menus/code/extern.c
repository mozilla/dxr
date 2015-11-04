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
  int fib(int n);
};

int MyClass::fib(int n) {
  return (n <= 1)? 1: fib(n-1) + fib(n-2);
}

namespace Space {
  void foo() {}
}
namespace Bar = Space;

#define MACRO "polo"
