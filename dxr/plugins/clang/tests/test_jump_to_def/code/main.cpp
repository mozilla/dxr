#include "foo.h"

void baz(int a) { return; }

int main(int argc, char* argv[]) {

  foo f;
  f.bar(1, 1);
  baz(1);
  return 0;
}
