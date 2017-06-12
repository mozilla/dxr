#include "main2.h"
#include "main3.h"

static void foo() /* in main2 */
{
}

void bar()
{
    foo();  /* calling foo in main2 */
    baz();
}
