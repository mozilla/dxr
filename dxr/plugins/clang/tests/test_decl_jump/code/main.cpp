#include "shared.h"

struct type_in_main
{
};

int var_in_main = 1;

void function_in_main()
{
}

int main()
{
  function_in_second();
  return 0;
}
