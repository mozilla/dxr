#!/bin/sh -e
# Install LLVM 3.2 from the binary tarball on llvm.org. Though there is an
# xorg-edgers 3.2 PPA for LLVM, there's none for clang.

if [ ! -f /usr/local/.llvm_is_installed ]; then
    cd /tmp
    wget http://llvm.org/releases/3.2/clang+llvm-3.2-x86_64-linux-ubuntu-12.04.tar.gz
    tar -zxf clang+llvm-3.2-x86_64-linux-ubuntu-12.04.tar.gz
    cd clang+llvm-3.2-x86_64-linux-ubuntu-12.04
    mv bin/* /usr/local/bin/
    mkdir -p /usr/local/docs
    mv docs/* /usr/local/docs/
    mv include/* /usr/local/include/
    mv lib/* /usr/local/lib/
    mkdir -p /usr/local/man/man1
    mv share/man/man1/* /usr/local/share/man/man1/

    touch /usr/local/.llvm_is_installed
fi
