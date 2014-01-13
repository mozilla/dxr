#include "main2.h"

namespace
{
    void foo() /* in main */
    {
    }
}

int main()
{
    foo();  /* calling foo in main */
    bar();
    return 0;
}
