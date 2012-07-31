#!/bin/sh

if [ -n "${DXR_ENV_SET}" ]; then
  unset CC
  unset CXX
fi

