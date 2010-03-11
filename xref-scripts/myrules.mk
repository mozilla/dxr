# Add support for generating xref info from idl
$(XPIDL_GEN_DIR)/%.h: %.idl $(XPIDL_COMPILE) $(XPIDL_GEN_DIR)/.done
	$(REPORT_BUILD)
	$(ELOG) $(XPIDL_COMPILE) -m header -w $(XPIDL_FLAGS) -o $(XPIDL_GEN_DIR)/$* $(_VPATH_SRCS)
	$(ELOG) $(XPIDL_COMPILE) -m xref -w $(XPIDL_FLAGS) -o $(XPIDL_GEN_DIR)/$* $(_VPATH_SRCS)
	@if test -n "$(findstring $*.h, $(EXPORTS) $(SDK_HEADERS))"; \
	  then echo "*** WARNING: file $*.h generated from $*.idl overrides $(srcdir)/$*.h"; else true; fi

jsexport::
	+$(LOOP_OVER_PARALLEL_DIRS)
	+$(LOOP_OVER_DIRS)

# JS exporting rules and setup
JSEXPORT := $(DIST)/jsfiles

# XXX: hard coded for now, fixme 
JSTOOLDIR := /var/www/html/dxr/xref-scripts

ifdef XPI_NAME
JSEXPORT := $(JSEXPORT)/$(XPI_NAME)
endif

$(JSEXPORT):
	$(NSINSTALL) -D $@
jsexport:: $(JSEXPORT)

ifdef EXTRA_COMPONENTS
jsexport:: $(EXTRA_COMPONENTS)
	$(INSTALL) $(IFLAGS1) $^ $(JSEXPORT)/components
endif
ifdef EXTRA_PP_COMPONENTS
jsexport:: $(EXTRA_PP_COMPONENTS)
	$(NSINSTALL) -D $(JSEXPORT)/components
	for i in $^; do \
		dest=$(JSEXPORT)/components/`basename $$i`; \
		$(RM) -f $$dest; \
		PYTHONPATH=$(topsrcdir)/config:$$PYTHONPATH $(PYTHON) $(JSTOOLDIR)/NicePreprocessor.py $(DEFINES) $(ACDEFINES) $(XULPPFLAGS) $$i > $$dest; \
	done
endif

ifdef EXTRA_JS_MODULES
libs:: $(EXTRA_JS_MODULES)
	$(INSTALL) $(IFLAGS) $^ $(JSEXPORT)/modules
endif
ifdef EXTRA_PP_JS_MODULES
jsexport:: $(EXTRA_PP_JS_MODULES)
	$(NSINSTALL) -D $(JSEXPORT)/modules
	for i in $^; do \
		dest=$(JSEXPORT)/modules/`basename $$i`; \
		$(RM) -f $$dest; \
		PYTHONPATH=$(topsrcdir)/config:$$PYTHONPATH $(PYTHON) $(JSTOOLDIR)/NicePreprocessor.py $(DEFINES) $(ACDEFINES) $(XULPPFLAGS) $$i > $$dest; \
	done
endif

ifneq (,$(wildcard $(JAR_MANIFEST)))
$(JSEXPORT)/chrome:
	$(NSINSTALL) -D $@
jsexport:: $(JSEXPORT)/chrome
	PYTHONPATH=$(topsrcdir)/config:$$PYTHONPATH $(PYTHON) $(JSTOOLDIR)/ChromeHacker.py \
		$(QUIET) -j $(JSEXPORT)/chrome \
		$(MAKE_JARS_FLAGS) $(XULPPFLAGS) $(DEFINES) $(ACDEFINES) \
		$(JAR_MANIFEST)
endif
