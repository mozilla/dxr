#!/bin/sh

if [ -z $1 ]; then
	echo "You should specify a compiler to run!";
	echo ""
	echo "usage: cc.sh <compiler> <SRCDIR> [other flags ...]"
	exit 1;
fi

if [ -z $2 ]; then
	echo "You should specify a source directory!";
	echo ""
	echo "usage: cc.sh <compiler> <SRCDIR> [other flags ...]"
	exit 1;
fi

FLAGS="-Xclang -load -Xclang $DXRSRC/xref-tools/cxx-clang/libclang-index-plugin.so -Xclang -add-plugin -Xclang dxr-index -Xclang -plugin-arg-dxr-index -Xclang $2"

compiler=$1
shift;
shift;

$compiler $FLAGS $*
