#include "template_foo.h"

//// Template instantiation and specialization:
void doit() {
  char aa = 'a';

  fud(Baz<int>());
  fud(aa);
  fud(3);

  Baz<int> bb;
  guz(bb);

  Gub gg;
  gg.bug(2);
  gg.bug(aa);

  Gleb<char> gl;
  gl.lerb(true);
  gl.lerb(3);

  Derb<int> cc;
  cc.flarb(3);
  Derb<char *> dd;
  dd.flarb(&aa);
}
