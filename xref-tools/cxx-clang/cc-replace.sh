#!/bin/bash

orig="$1"
shift
$DXRSRC/xref-tools/cxx-clang/clang-dump-sql "$@"
"$1" "$@"
