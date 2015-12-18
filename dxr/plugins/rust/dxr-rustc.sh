if echo $@ | grep -q "build.rs"; then
    rustc "$@"
else
    rustc -Zsave-analysis "$@"
fi
