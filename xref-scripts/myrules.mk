# Add support for generating xref info from idl
$(XPIDL_GEN_DIR)/%.h: %.idl $(XPIDL_COMPILE) $(XPIDL_GEN_DIR)/.done
	$(REPORT_BUILD)
	$(ELOG) $(XPIDL_COMPILE) -m header -w $(XPIDL_FLAGS) -o $(XPIDL_GEN_DIR)/$* $(_VPATH_SRCS)
	$(ELOG) $(XPIDL_COMPILE) -m xref -w $(XPIDL_FLAGS) -o $(XPIDL_GEN_DIR)/$* $(_VPATH_SRCS)
	@if test -n "$(findstring $*.h, $(EXPORTS) $(SDK_HEADERS))"; \
	  then echo "*** WARNING: file $*.h generated from $*.idl overrides $(srcdir)/$*.h"; else true; fi

