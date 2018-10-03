struct type_in_main;
struct type_in_second;

extern int var_in_main;
extern int var_in_second;

void function_in_main();
void function_in_second();

/*
 * We want to test the situation where a function has a decldef with no defloc
 * followed by a decldef with a defloc.
 *
 * This file contains declarations for two different functions defined in two
 * different source files.  When compiling main.cpp the output for this file
 * will look like:
 *     decldef,name,"function_in_main",...,defloc,"main.cpp:3:5",...
 *     decldef,name,"function_in_second",...
 * (where the "function_in_second" line has no defloc).
 *
 * When compiling second.cpp the output for this file will look like:
 *     decldef,name,"function_in_main",...
 *     decldef,name,"function_in_second",...,defloc,"second.cpp:3:5",...
 * (where the "function_in_main" line has no defloc).
 *
 * We can't count on which of these two files will be processed first.  If we
 * process main.cpp first then function_in_second will serve as our test
 * function.  If we process second.cpp first then function_in_main will serve
 * as our test case.  No matter which order we process the files in we are
 * guaranteed to have one function that will work as an effective test.
 *
 */
