#!/bin/bash

# XXX: I don't know if this is bash-only, but that's the only shell I use. So
# assume it is.

if [ -z "$1" ]; then
  echo "Usage: . $0 <srcdir>"
fi
SRCDIR="$1"

if [ -z "$DXRSRC" ]; then
  echo "Setting DXRSRC variable"
  export DXRSRC=$(dirname $(readlink -f $0))
fi

echo "Finding available DXR plugins..."
tools=( $(python - <<HEREDOC
import dxr
files = [x.__file__ for x in dxr.get_active_plugins(None, '$DXRSRC')]
print ' '.join([x[:x.find('/indexer.py')] for x in files])
HEREDOC
) )
echo -n "Found:"
for plugin in $(seq 0 $((${#tools[@]} - 1))); do
  echo -n " $(basename ${tools[plugin]})"
done
echo ""

for plugin in $(seq 0 $((${#tools[@]} - 1))); do
  echo -n "Prebuilding $(basename ${tools[plugin]})... "
  make -s -C ${tools[plugin]} prebuild
  if [[ $? != 0 ]]; then
    echo "Bailing!"
    return 1
  fi
  echo "done!"
done

echo -n "Preparing environment... "
for plugin in $(seq 0 $((${#tools[@]} - 1))); do
  . "${tools[plugin]}/set-env.sh"
done
echo "done!"

echo "DXR setup complete. You can now compile your source code in this shell."

# Check for . $0 instead of ./$0
return 0 &>/dev/null
echo -e "\n\n\n\n\e[1;31mYour environment is not correctly set up.\e[0m\n"
echo "You need to run the following command instead:"
echo ". $DXRSRC/setup-env.sh"
