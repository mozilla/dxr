ifneq ($(XPIDLSRCS),)
ifndef $(MOZILLA_DIR)
  MOZILLA_DIR := $(topsrcdir)
endif
$(XPIDL_GEN_DIR)/%.idlcsv: %.idl $(DXRSRC)/xref-tools/moztools/idl_xref.py
	$(PYTHON) $(MOZILLA_DIR)/config/pythonpath.py \
		-I$(MOZILLA_DIR)/other-licenses/ply \
		-I$(MOZILLA_DIR)/xpcom/idl-parser \
		$(DXRSRC)/xref-tools/moztools/idl_xref.py --cachedir=$(MOZILLA_DIR)/xpcom/idl-parser $(XPIDL_FLAGS) $(_VPATH_SRCS) > $@

export:: $(patsubst %.idl,$(XPIDL_GEN_DIR)/%.idlcsv, $(XPIDLSRCS))
endif
