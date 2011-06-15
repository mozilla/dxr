#!/usr/bin/env python2.6

import json

class Location:
  """ A source location, e.g., path/to/file.cpp:45. """
  def __init__(self, path, loc=None):
    if path is None or path == '':
      self.path = self.loc = self.full = ''
    else:
      if loc:
        self.path = path
        self.loc = loc
        self.full = path + ':' + `loc`
      else:
        self.path, self.loc = path.split(':')[:2]
        self.full = path

  def __str__(self):
    return self.full

class DxrTypeRelation:
    DIRECT_BASE = 'direct_base'
    INDIRECT_BASE = 'indirect_base'
    DIRECT_DERIVED = 'direct_derived'
    INDIRECT_DERIVED = 'indirect_derived'

    def __init__(self, first, second, relation):
        self.first = first
        self.second = second
        self.relation = relation

    class JSONEncoder(json.JSONEncoder):
      ''' a custom JSON encoder for DxrTypeRelations objects '''
      def default(self, relation):
         if isinstance (relation, DxrTypeRelation):
           return {'direct': relation.relation in [DxrTypeRelation.DIRECT_BASE, DxrTypeRelation.DIRECT_DERIVED],
                   'type': relation.second}
         return json.JSONEncoder.default(self, relation)

    class DojoEncoder(json.JSONEncoder):
      ''' a custom Dojo-style JSON encoder for DxrTypeRelations objects '''
      def default(self, relation):
         if isinstance (relation, DxrTypeRelation):
           return {'label': relation.second.name,
                   'url': relation.second.loc.full,
                   'icon': 'icon-base'}

         return json.JSONEncoder.default(self, relation)


class DxrType:
  @classmethod
  def find(cls, typename, conn, loc=None):
    row = None
    if loc:
      row = conn.execute('select tqualname, tloc, tkind from types where tqualname=? and tloc=?;', 
                         (typename,loc)).fetchone()
    else:
      row = conn.execute('select tqualname, tloc, tkind from types where tqualname=?;',
                         (typename,)).fetchone()

    if not row:
      return None

    return DxrType(row[0], row[1], None, None, row[2], None, conn)

  def __init__(self, name, loc, typedef, typedef_loc, kind, template, conn):
    self.name = name
    self.loc = Location(loc)
    self.typedef = typedef
    self.typedef_loc = Location(typedef_loc)
    self.kind = kind
    self.template = template
    self.conn = conn
    self.scopeid = conn.execute('SELECT scopeid FROM scopes WHERE ' +
      'sname=? AND sloc=?', (name, loc)).fetchone()[0]

    # Lazy load these...
    self.users = None
    self.members = None
    self.bases = None
    self.derived = None

  class JSONEncoder(json.JSONEncoder):
     ''' a custom JSON encoder for DxrType objects '''
     def default(self, t):
         if isinstance (t, DxrType):
           return {'direct': relation.relation in [DxrTypeRelation.DIRECT_BASE, DxrTypeRelation.DIRECT_DERIVED],
                   'type': relation.second}
         return json.JSONEncoder.default(self, t)

  class DojoEncoder(json.JSONEncoder):
     ''' a custom Dojo-style JSON encoder for DxrType objects '''
     def default(self, t):
         if isinstance (t, DxrType):
           children = [{'label': t.loc.full,
                         'url': t.loc.full,
                         'icon': 'icon-decl'}]

           if t.typedef:
             children.append({'label': 'Typedef - ' + t.typedef, 'url': t.typedef_loc.full, 'icon': 'icon-type'})

           if t.template:
             children.append({'label': 'Template - ' + t.template, 'icon': 'icon-type'})

           if len(t.getMembers()):
             children.append({'label': 'Members', 'icon': 'icon-member', 'children': t.getMembers()})

           if len(t.getBases()):
             children.append({'label': 'Bases', 'icon': 'icon-base', 'children': t.getBases()})

           if len(t.getDerived()):
             children.append({'label': 'Derived', 'icon': 'icon-base', 'children': t.getDerived()})

           if len(t.getUsers(limit=25)):
             children.append({'label': 'Users', 'icon': 'icon-user', 'children': t.getUsers(limit=25)})

           jsonString = {'label': t.name,
                         'icon': 'icon-type'}
           if len(children):
             jsonString['children'] = children 
           
           return jsonString
             
         # Make sure we use the right DojoEncoder for contained types
         elif isinstance (t, DxrUser):
           e = DxrUser.DojoEncoder()
           return e.default(t)
         elif isinstance (t, DxrTypeRelation):
           e = DxrTypeRelation.DojoEncoder()
           return e.default(t)
         elif isinstance (t, DxrMember):
           e = DxrMember.DojoEncoder()
           return e.default(t)

         return json.JSONEncoder.default(self, t)

  def getMembers(self):
    if self.members:
      return self.members

    self.members = []
    for row in self.conn.execute('SELECT fname, flongname, floc ' +
        'FROM functions WHERE scopeid=' + str(self.scopeid)):
      self.members.append(DxrMember(row[1], row[0], self, row[2], None, self.conn))
    for row in self.conn.execute('SELECT vname, vloc ' +
        'FROM variables WHERE scopeid=' + str(self.scopeid)):
      self.members.append(DxrMember(row[0], row[0], self, row[1], None, self.conn))
    #for row in self.conn.execute('select mname, mshortname, mdecl, mdef, mvalue from members where mtname=? and mtloc=?;',
    #                             (self.name, self.loc.full)):
    #  self.members.append(DxrMember(row[0], row[1], self, row[3], row[4], self.conn))

    return self.members

  def getBases(self):
    if self.bases:
      return self.bases

    self.bases = []
    relation = None

    # Direct bases
    sql = 'select tqualname, tloc, tkind from types where tname in ' + \
          '(select tbname from impl where tcname=? and tcloc=? and direct=1);'
    
    for row in self.conn.execute(sql, (self.name, self.loc.full)).fetchall():
      self.bases.append(DxrTypeRelation(self, DxrType(row[0], row[1], None, None, row[2], None, self.conn), DxrTypeRelation.DIRECT_BASE))

    # Indirect Bases
    sql = 'select tqualname, tloc, tkind from types where tname in ' + \
          '(select tbname from impl where tcname=? and tcloc=? and not direct=1);'
    
    for row in self.conn.execute(sql, (self.name, self.loc.full)).fetchall():
      self.bases.append(DxrTypeRelation(self, DxrType(row[0], row[1], None, None, row[2], None, self.conn), DxrTypeRelation.INDIRECT_BASE))

    return self.bases

  def getDerived(self):
    if self.derived:
      return self.derived

    self.derived = []
    relation = None

    # Types directly derived from this type.
    sql = 'select tqualname, tloc, tkind from types where tname in ' + \
          '(select tcname from impl where tbname=? and tbloc=? and direct = 1);'
    
    for row in self.conn.execute(sql, (self.name, self.loc.full)):
      self.derived.append(DxrTypeRelation(self, DxrType(row[0], row[1], None, None, row[2], None, self.conn), DxrTypeRelation.DIRECT_DERIVED))

    # Types indirectly derived from this type.
    sql = 'select tqualname, tloc, tkind from types where tname in ' + \
          '(select tcname from impl where tbname=? and tbloc=? and not direct = 1);'
    
    for row in self.conn.execute(sql, (self.name, self.loc.full)):
      self.derived.append(DxrTypeRelation(self, DxrType(row[0], row[1], None, None, row[2], None, self.conn), DxrTypeRelation.INDIRECT_DERIVED))

    return self.derived

  def getUsers(self, limit=None):
    if self.users:
      return self.users

    self.users = []
    limitClause = ''
    if limit:
      limitClause = 'LIMIT ' + `limit`

    sql = "SELECT refloc FROM refs WHERE refid=? %s;" % limitClause
    for row in self.conn.execute(sql, (self.name,)):
      self.users.append(DxrUser('', Location(row[1])))
    
    return self.users

  def dojoJson(self):
    pass

class DxrUser:
  def __init__(self, func, location):
    self.func = func
    self.loc = location

  class JSONEncoder(json.JSONEncoder):
     ''' a custom JSON encoder for DxrUser objects '''
     def default(self, user):
         if isinstance (user, DxrUser):
           return {'func': user.func,
                   'loc': user.loc.full}
         return json.JSONEncoder.default(self, user)

  class DojoEncoder(json.JSONEncoder):
     ''' a custom Dojo-style JSON encoder for DxrUser objects '''
     def default(self, user):
         if isinstance (user, DxrUser):
           return {'label': user.func,
                   'icon': 'icon-user',
                   'url': user.loc.full}
         return json.JSONEncoder.default(self, user)


class DxrMember:
  def __init__(self, name, shortname, dxr_type, defn, value, conn):
    self.name = name
    self.shortname = shortname
    self.type = dxr_type
    self.defn = Location(defn)
    self.value = value
    self.conn = conn
    self.implementations = None

  class JSONEncoder(json.JSONEncoder):
     ''' a custom JSON encoder for DxrMember objects '''
     def default(self, member):
         if isinstance (member, DxrMember):
           return {'name': member.name, 
                   'shortname': member.shortname,
                   #'type': {'name': member.type.name, 'loc': member.type.loc.full},
                   'defn': member.defn.full,
                   'value': member.value,
                   'implementations': member.getDerivedImplementations()}
         return json.JSONEncoder.default(self, member)

  class DojoEncoder(json.JSONEncoder):
     ''' a custom Dojo-style JSON encoder for DxrMember objects '''
     def default(self, m):
         if isinstance (m, DxrMember):
           impls = None
           if len(m.getDerivedImplementations(includeTypeName=True)):
             impls = {'label': 'Implementations', 'icon': 'icon-member', 'children': m.getDerivedImplementations(includeTypeName=True)}
             
           jsonString = {'label': m.name,
                         #'type': m.type.name,
                         'icon': 'icon-member', 
                         'shortname': m.shortname, 
                         'value': m.value}
           jsonString['children'] = [{'label': m.defn.full, 'icon': 'icon-def', 'url': m.defn.full}]

           if impls:
             jsonString['children'].append(impls)
           
           return jsonString
                            
         return json.JSONEncoder.default(self, m)


  def getDerivedImplementations(self, includeTypeName=False):
    if self.implementations:
      return self.implementations
    
    self.implementations = []
    
    # XXX: fixme
    return self.implementations

#  def getUsers(self):
#    if self.users:
#      return self.users
#
#    self.users = []
#    
#    sql = 'select namespace, type, shortName from node where id in ' + \
#          '(select caller from edge where callee in '+ \
#          '(select id from node where type=? COLLATE NOCASE and shortName=? COLLATE NOCASE));'
#    
#    for row in conn.execute(sql, (self.type.name, self.shortname)).fetchall():
#      self.users.append(DxrUser

class DxrStatement:
  @classmethod
  def find(cls, file, line, name, conn):
    sql = 'select vname, vshortname, vtype, vtloc, vfuncname, vfuncloc, vlocf, vlocl, vdeclloc, visFcall,' + \
          'vmember from stmts where vlocf=? and vlocl=? and vshortname=?;'
    row = conn.execute(sql, (file, line, name)).fetchone()
    if not row:
      return None

    # strip pointer from type name (e.g., nsIFoo* is really nsCOMPtr<nsIFoo> but we need nsIFoo)
    typename = row[2]
    if typename.endswith('*'):
      typename = typename[0:-1]

    return DxrStatement(row[0], row[1], DxrType.find(typename, conn, loc=row[3]), row[4], row[5], row[6] + ':' + `row[7]`, conn)

  def __init__(self, name, shortname, dxr_type, func, funcloc, decl, conn):
    self.name = name
    self.shortname = shortname
    self.type = dxr_type
    self.func = func
    self.funcloc = Location(funcloc)
    self.decl = Location(decl)
    self.conn = conn

  # TODO -- have not touched this yet....
  class JSONEncoder(json.JSONEncoder):
     ''' a custom JSON encoder for DxrMember objects '''
     def default(self, member):
         if isinstance (member, DxrMember):
           return {'name': member.name, 
                   'shortname': member.shortname,
                   'type': {'name': member.type.name, 'loc': member.type.loc.full},
                   'decl': member.decl.full,
                   'defn': member.decl.full,
                   'value': member.value,
                   'implementations': member.getDerivedImplementations()}
         return json.JSONEncoder.default(self, member)

  class DojoEncoder(json.JSONEncoder):
     ''' a custom Dojo-style JSON encoder for DxrStatement objects '''
     def default(self, s):
#         if isinstance (s, DxrType):
#           e = DxrType.DojoEncoder()
#           return e.default(s)
         if isinstance (s, DxrStatement):
           return {'label': s.decl.full,
                   'url': s.decl.full,
                   'icon': 'icon-decl', 
                   'children': s.type}
                            
         return DxrType.DojoEncoder().default(s)
