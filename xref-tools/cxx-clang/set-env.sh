#!/bin/sh

export CC="$DXRSRC/xref-tools/cxx-clang/cc.sh clang $SRCDIR"
export CXX="$DXRSRC/xref-tools/cxx-clang/cc.sh clang++ $SRCDIR"
export DXR_INDEX_OUTPUT="$OBJDIR"
export DXR_ENV_SET="true"
