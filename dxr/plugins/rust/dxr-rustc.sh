if echo $@ | egrep -q "build.rs|lib.rs"; then
    rustc "$@"
else
    rustc -Zsave-analysis "$@"
fi
