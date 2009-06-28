#!/usr/bin/perl

# Convert the result of xpidl_xref to .sql
# Usage: process_xref.pl srcdir < file

$srcdir=shift;
$srcdir .= '/' unless $srcdir =~ m|/$|;

my $tmp, $base;
my $mtname, $mtloc;
my $mname, $mdecl;

# lines will looke like this: string1 string2\n

while (<>) {
    chomp($_);
    ($loc, $tmp) = split(/ /, $_, 2);

    # Genericize loc, removing source root
    $loc =~ s|^$srcdir(.+)$|$1|eg;

    # NOTE: interfaces decls are always encountered before interface members (I rely on this order)
    if ($tmp =~ m/^[^ :|]+$/) {
        # /home/dave/mozilla-central/src/toolkit/mozapps/extensions/public/nsIExtensionManager.idl:486 nsIFoo    
        $mtloc = $loc;
        $mtname = $tmp;
	($mtmodule=$loc) =~ s|/[^/]*:[0-9]+ *$||;
        print "delete from types where tname='$mtname';\n";
        print "delete from members where mtname='$mtname';\n";
        print "insert or abort into types ('tname','tloc','tkind','ttemplate','tignore','tmodule') values('$mtname','$loc','interface','','0','$mtmodule');\n";
        print "update impl set tbloc='$loc' where tbname='$mtname';\n";
        print "update impl set tcloc='$loc' where tcname='$mtname';\n";
        # For statements, I treat nsCOMPtr<nsIFoo> as nsIFoo*, so also look for mtname*
        print "update stmts set vtloc='$loc' where vtype='$mtname' or vtype='$mtname*';\n";
        print "update stmts set vmemberloc='$loc' where vmember='$mtname';\n";
        print "update stmts set vdeclloc='$loc' where vmember='$mtname';\n";
    } elsif($tmp =~ /^typedef.+$/) {
        # /home/dave/dxr/mozilla-central/mozilla/xpcom/base/nsrootidl.idl:74 typedef|PRUint32|nsresult
        ($mtmodule=$loc) =~ s|/[^/]*:[0-9]+ *$||;
        (undef, $mtype, $mname) = split(/\|/, $tmp, 3);
        print "insert or abort into types ('tname','tloc','ttypedefname','tkind','tignore','tmodule') values('$mname','$loc','$mtype','typedef','0','$mtmodule');\n";
        # XXX: This will give us a loc, but maybe not the right one, if there are multiple types with the same name
        print "update types set ttypedefloc=(select tloc from types where tname='$mtype' limit 1) where tname='$mname';\n";
    } elsif($tmp =~ m/^[^ :]+ : [^ :]+$/) {
        # /home/dave/mozilla-central/src/toolkit/mozapps/extensions/public/nsIExtensionManager.idl:486 nsIFoo : nsIBar
        ($mtname, $base) = split(/ : /, $tmp);
        $mtloc = $loc;
	($mtmodule=$loc) =~ s|/[^/]*:[0-9]+ *$||;

        print "delete from types where tname='$mtname';\n";
        print "delete from members where mtname='$mtname';\n";
        print "insert or abort into types ('tname','tloc','tkind','tmodule') values('$mtname','$loc','interface','$mtmodule');\n";   
        print "update impl set tbloc='$loc' where tbname='$mtname';\n";
        print "update impl set tcloc='$loc' where tcname='$mtname';\n";
        # For statements, I treat nsCOMPtr<nsIFoo> as nsIFoo*, so also look for mtname*
        print "update stmts set vtloc='$loc' where vtype='$mtname' or vtype='$mtname*';\n";
        print "update stmts set vmemberloc='$loc' where vmember='$mtname';\n";
        print "update stmts set vdeclloc='$loc' where vmember='$mtname';\n";
    } elsif($tmp =~ m/^enum .+$/) {
        # /home/dave/dxr/mozilla-central/mozilla/accessible/public/nsIAccessibleRole.idl:784 enum ROLE_LAST_ENTRY 122U
        (undef, $mname, $mvalue) = split(/ /, $tmp, 3);
        # remove enum value already there from _xpidlgen/nsIFoo.h and replace with better info from idl directly
        print "delete from members where mtname='undefined' and mname='$mname';\n";
        print "insert or abort into members ('mtname','mtloc','mname','mshortname','mdecl','mvalue') values('$mtname','$mtloc','$mname','$mname','$loc','$mvalue');\n";
    } else {
        # /home/dave/mozilla-central/src/toolkit/mozapps/extensions/public/nsIExtensionManager.idl:492 nsIUpdateItem::id
        ($mtname, $mname) = split(/::/, $tmp);
        ($mshortname=$mname) =~ s/\(.*$//;
        print "insert or abort into members ('mtname','mtloc','mname','mshortname','mdecl') values('$mtname','$mtloc','$mname','$mshortname','$loc');\n";
    }
}
