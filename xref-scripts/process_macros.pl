#!/usr/bin/perl
use IPC::Open2;

# process_macros.pl < .macros-file

my $name, $value;

# lines will looke like this: #define SCOPE_MAKE_UNIQUE_SHAPE(cx,scope) ((scope)->shape = js_GenerateShape((cx), JS_FALSE, NULL))\n
while (<>) {
    chomp;
    
    # skip any warnings, there are a few known (e.g., 'warning: anonymous variadic macros were introduced in C99' for
    # stuff like - #define verbose_only(...) )
    next if ($_ !~ m/^#define/);

    (undef, $name, $value) = split(/ /, $_ ,3);

    # ignore header guards and other macros with empty definitions
    next if $value eq '';

    # pass value to indent to pretty print (indent will choke on many of these fragments, throw out errs)
    # NOTE: there are easier ways to do this, but I want to be careful with untrusted source
    my $pid = open2(READ, WRITE, 'indent -orig --indent-level2 --line-length80 2>/dev/null');
    print WRITE $value;
    close WRITE;
    my @output=<READ>;
    close READ; 
    waitpid $pid, 0;
    $value = join("",@output), "\n";

    # remove final newline
    chomp $value;

    # drop any arguments from the macro name, since we'll get just the name token in source:
    # #define JS_STATIC_ASSERT(cond) typedef int JS_STATIC_ASSERT_GLUE(js_static_assert, __COUNTER__)[(cond) ? 1 : -1]
    # use JS_STATIC_ASSERT without (cond)
    ($shortname = $name) =~ s|\([^\)]*\)||;

    # escape single quotes for sql statement
    $value =~ s/'/''/g;

    print "insert or abort into macros ('mname','mshortname', 'mvalue') values('$name','$shortname','$value');\n";
}
