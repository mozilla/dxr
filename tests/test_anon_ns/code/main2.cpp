#include "main2.h"

namespace
{
    void foo() /* in main2 */
    {
    }
}

void bar()
{
    foo();  /* calling foo in main2 */
}
