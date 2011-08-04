#!/bin/sh

export CC="clang -Xclang -load -Xclang $DXRSRC/xref-tools/cxx-clang/libclang-index-plugin.so -Xclang -add-plugin -Xclang dxr-index -Xclang -plugin-arg-dxr-index -Xclang $SRCDIR"
export CXX="clang++ -Xclang -load -Xclang $DXRSRC/xref-tools/cxx-clang/libclang-index-plugin.so -Xclang -add-plugin -Xclang dxr-index -Xclang -plugin-arg-dxr-index -Xclang $SRCDIR"
export DXR_INDEX_OUTPUT="$OBJDIR"
export DXR_ENV_SET="true"
