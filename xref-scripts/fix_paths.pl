#!/usr/bin/perl

# Follows objdir symlinks back to source files and fixes paths in .sql files
# Usage: fix_paths.pl srcdir objdir < file

use Cwd "realpath";

$srcdir=shift;
$srcdir .= '/' unless $srcdir =~ m|/$|;
$objdir=shift;
$objdir .= '/' unless $objdir =~ m|/$|;

# Figure out where dist is.  Assume mozilla-central (objdir/dist)
$dist = 'dist';
if (-d $objdir.'mozilla/dist') {
    # comm-central
    $dist = 'mozilla/dist';
}

while (<>) {
    # File linked locally in same dir (e.g., xpcom/glue) 
    s|'([^'/]+\.cpp):|"'".realpath($1).":"|eg;

    # Files symlinked into dist/include or dist/sdk (with and without prefix) 
    s|'[^']*/?($dist/sdk/include/[^:']*):|"'".realpath($objdir.$1).":"|eg;
    s|'[^']*/?($dist/include/[^:']*):|"'".realpath($objdir.$1).":"|eg;
    s|"'(/[^'/ ]+/$dist/include/[^:']*):"|"'".realpath($1).":"|eg;
    
    # Genericize paths, removing source root
    s|'$srcdir([^']+)'|"'".$1."'"|eg;

    # Replace 'fixme' in tmodule with type's source location (not file+loc)
    # insert or abort into types ('tname','tloc','tkind','tmodule') values('nsISupports','xpcom/base/nsISupportsBase.h:66','class','fixme');
    m|'([^:']+):\d+'|;
    my $dir = $1;
    $dir =~ s|/[^/]+\.[^']+||eg;
    s|'fixme'|"'".$dir."'"|eg;

    print;
}
