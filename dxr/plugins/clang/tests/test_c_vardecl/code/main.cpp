#include <stdio.h>
#include "extern.h"

// Hello World Example
int main(int argc, char* argv[]){
  set_global();
  printf("Hello World");
  return global;
}
