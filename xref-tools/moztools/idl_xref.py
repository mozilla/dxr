# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is mozilla.org code.
#
# The Initial Developer of the Original Code is
#   Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2011
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Benjamin Smedberg <benjamin@smedbergs.us>
#   Joshua Cranmer <Pidgeot18@gmail.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either of the GNU General Public License Version 2 or later (the "GPL"),
# or the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

"""
Given XPIDL files, print basic information in machine-readable form for
consumption by DXR and combination with dehydra-based type information.

output:
/path/to/file.idl:lineno interfacename : baseinterface
/path/to/file.idl:lineno interfacename::MethodName(signature)
/path/to/file.idl:lineno enum ENUM_NAME valueU

...and possibly more
"""

import csv, sys, os.path, re, xpidl, header

def print_xref(idl, writer):
  # Top-level productions
  for p in idl.productions:
    if p.kind == 'interface':
      print_interface_xref(p, writer)
    # XXX; typedef, native

def print_interface_xref(iface, writer):
  if iface.namemap is None:
    raise Exception("Interface was not resolved.")

  row = ['interface', 'name', iface.name]
  if iface.base is not None:
    row += ['ibase', iface.base]
  row += ['iloc', iface.location._file + ':' + str(iface.location._lineno)]
  row += ['uuid', iface.attributes.uuid]
  writer.writerow(row)

  for m in iface.members:
    if isinstance(m, xpidl.CDATA):
      continue
    row = ['']
    row += ['loc', m.location._file + ':' + str(m.location._lineno)]
    row += ['iface', iface.name]
    row += ['name', m.name]
    if isinstance(m, xpidl.ConstMember):
      row[0] = 'const'
      row += ['value', m.getValue()]
      row += ['type', m.type]
    elif isinstance(m, xpidl.Attribute):
      row[0] = 'attr'
      row += ['type', m.type]
      row += ['readonly', m.readonly and 'true' or 'false']
    elif isinstance(m, xpidl.Method):
      row[0] = 'method'
      row += ['type', m.type]
    writer.writerow(row)

if __name__ == '__main__':
  from optparse import OptionParser
  o = OptionParser()
  o.add_option('-I', action='append', dest='incdirs', help="Directory to search for imported files", default=[])
  o.add_option('--cachedir', dest='cachedir', help="Directory in which to cache lex/parse tables.", default='')
  options, args = o.parse_args()
  file, = args

  if options.cachedir != '':
      sys.path.append(options.cachedir)

  p = xpidl.IDLParser(outputdir=options.cachedir)
  idl = p.parse(open(file).read(), filename=file)
  idl.resolve(options.incdirs, p)
  print_xref(idl, csv.writer(sys.stdout))
