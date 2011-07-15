#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: . $0 <srcdir> [<datadir>]"
  return 1
  exit 1
fi
SRCDIR="$1"

if [ -z "$2" ]; then
  export OBJDIR="$1"
else
  export OBJDIR="$2"
fi

if [ -z "$DXRSRC" ]; then
  echo "Setting DXRSRC variable"
  scriptsrc=${BASH_SOURCE[0]}
  export DXRSRC=$(dirname $(readlink -f $scriptsrc))
fi

echo "Finding available DXR plugins..."
tools=( $(PYTHONPATH=$DXRSRC:$PYTHONPATH python - <<HEREDOC
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
  if [ -e ${tools[plugin]}/Makefile ]; then 
    make -s -C ${tools[plugin]} prebuild
    if [[ $? != 0 ]]; then
      echo "Bailing!"
      return 1
    fi
  fi
  echo "done!"
done

echo -n "Preparing environment... "
for plugin in $(seq 0 $((${#tools[@]} - 1))); do
  if [ -e "${tools[plugin]}/set-env.sh" ]; then
    . "${tools[plugin]}/set-env.sh"
  fi
done
echo "done!"

echo "DXR setup complete. You can now compile your source code in this shell."

# Check for . $0 instead of ./$0
return 0 &>/dev/null
echo -e "\n\n\n\n\e[1;31mYour environment is not correctly set up.\e[0m\n"
echo "You need to run the following command instead:"
echo ". $DXRSRC/setup-env.sh"
