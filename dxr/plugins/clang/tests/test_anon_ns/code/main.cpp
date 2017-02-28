#include "main2.h"
#include "main3.h"

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
    baz();
    return 0;
}
