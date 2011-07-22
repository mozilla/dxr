ifneq ($(XPIDLSRCS),)
xpidldir := $(if $(wildcard $(topsrcdir)/mozilla),$(topsrcdir)/mozilla,$(topsrcdir))
$(XPIDL_GEN_DIR)/%.idlcsv: %.idl $(DXRSRC)/xref-tools/moztools/idl_xref.py
	$(PYTHON) $(xpidldir)/config/pythonpath.py \
		-I$(xpidldir)/other-licenses/ply \
		-I$(xpidldir)/xpcom/idl-parser \
		$(DXRSRC)/xref-tools/moztools/idl_xref.py --cachedir=$(xpidldir)/xpcom/idl-parser $(XPIDL_FLAGS) $(_VPATH_SRCS) > $@

export:: $(patsubst %.idl,$(XPIDL_GEN_DIR)/%.idlcsv, $(XPIDLSRCS))
endif
