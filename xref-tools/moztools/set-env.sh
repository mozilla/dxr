#!/bin/bash

if [ -e $SRCDIR/config/rules.mk ]; then
  OUTFILE=$OBJDIR/config/myrules.mk
  if [ ! -e $OBJDIR/config ]; then
    mkdir -p $OBJDIR/config
  fi
  
  NEEDS_OBJDIR=1
  if [ -e $OUTFILE ]; then
    if grep -q -- '-include $(DXRSRC)/xref-tools/moztools' $OUTFILE ; then
      NEEDS_OBJDIR=0
    fi
  fi
  
  if [ $NEEDS_OBJDIR -eq 1 ]; then
    echo '-include $(DXRSRC)/xref-tools/moztools/myrules.mk' >> $OUTFILE
  fi
fi
