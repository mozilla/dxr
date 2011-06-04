#!/bin/sh

export CC="clang -Xclang -load -Xclang $DXRSRC/xref-tools/cxx-clang/libclang-index-plugin.so -Xclang -add-plugin -Xclang dxr-index"
export CXX="clang++ -Xclang -load -Xclang $DXRSRC/xref-tools/cxx-clang/libclang-index-plugin.so -Xclang -add-plugin -Xclang dxr-index"
