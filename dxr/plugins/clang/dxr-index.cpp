#include "clang/AST/AST.h"
#include "clang/AST/ASTConsumer.h"
#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Basic/Version.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Frontend/FrontendPluginRegistry.h"
#include "clang/Lex/Lexer.h"
#include "clang/Lex/Preprocessor.h"
#include "clang/Lex/PPCallbacks.h"
#include "llvm/ADT/SmallString.h"
#include "llvm/Support/raw_ostream.h"

#include <iostream>
#include <map>
#include <sstream>
#include <stdio.h>
#include <stdlib.h>

// Needed for sha1 hacks
#include <fcntl.h>
#include <unistd.h>
#include "sha1.h"

#define CLANG_AT_LEAST(major, minor) \
  (CLANG_VERSION_MAJOR > (major) || (CLANG_VERSION_MAJOR == (major) && CLANG_VERSION_MINOR >= (minor)))

using namespace clang;

namespace {

const std::string GENERATED("--GENERATED--/");

// Curse whomever didn't do this.
std::string &operator+=(std::string &str, unsigned int i) {
  static char buf[15] = { '\0' };
  char *ptr = &buf[13];
  do {
    *ptr-- = (i % 10) + '0';
    i = i/10;
  } while (i > 0);
  return str += (ptr + 1);
}

inline bool str_starts_with(const std::string &s, const std::string &prefix) {
  return s.compare(0, prefix.size(), prefix) == 0;
}

inline bool str_ends_with(const std::string &s, const std::string &suffix) {
  return s.size() >= suffix.size() && s.compare(s.size() - suffix.size(), suffix.size(), suffix) == 0;
}

// BEWARE: use only as a temporary
const char *hash(std::string &str) {
  static unsigned char rawhash[20];
  static char hashstr[41];
  sha1::calc(str.c_str(), str.size(), rawhash);
  sha1::toHexString(rawhash, hashstr);
  return hashstr;
}

std::string srcdir;
std::string output;
std::string tmpdir; // Place to save all the csv files to

struct FileInfo {
  FileInfo(std::string &rname) : realname(rname) {
    interesting = rname.compare(0, srcdir.length(), srcdir) == 0;
    if (interesting) {
      // Remove the trailing `/' as well.
      realname.erase(0, srcdir.length() + 1);
    } else if (rname.compare(0, output.length(), output) == 0) {
      // We're in the output directory, so we are probably a generated header
      // We use the escape character to indicate the objdir nature.
      // Note that output also has the `/' already placed
      interesting = true;
      realname.replace(0, output.length(), GENERATED);
    }
  }
  std::string realname;
  std::ostringstream info;
  bool interesting;
};

class IndexConsumer;

class PreprocThunk : public PPCallbacks {
  IndexConsumer *real;
public:
  PreprocThunk(IndexConsumer *c) : real(c) {}
#if CLANG_AT_LEAST(3, 3)
  virtual void MacroDefined(const Token &tok, const MacroDirective *md);
  virtual void MacroExpands(const Token &tok, const MacroDirective *md, SourceRange range, const MacroArgs *ma);
  virtual void MacroUndefined(const Token &tok, const MacroDirective *md);
#if CLANG_AT_LEAST(3, 4)
  virtual void Defined(const Token &tok, const MacroDirective *md, SourceRange range);
#else
  virtual void Defined(const Token &tok, const MacroDirective *md);
#endif
  virtual void Ifdef(SourceLocation loc, const Token &tok, const MacroDirective *md);
  virtual void Ifndef(SourceLocation loc, const Token &tok, const MacroDirective *md);
#else
  virtual void MacroDefined(const Token &MacroNameTok, const MacroInfo *MI);
  virtual void MacroExpands(const Token &MacroNameTok, const MacroInfo *MI, SourceRange Range);
  virtual void MacroUndefined(const Token &tok, const MacroInfo *MI);
  virtual void Defined(const Token &tok);
  virtual void Ifdef(SourceLocation loc, const Token &tok);
  virtual void Ifndef(SourceLocation loc, const Token &tok);
#endif
virtual void InclusionDirective(  // same in 3.2 and 3.3
    SourceLocation hashLoc,
    const Token &includeTok,
    StringRef fileName,
    bool isAngled,
    CharSourceRange filenameRange,
    const FileEntry *file,
    StringRef searchPath,
    StringRef relativePath,
    const Module *imported);
};

class IndexConsumer : public ASTConsumer,
                      public RecursiveASTVisitor<IndexConsumer>,
                      public DiagnosticConsumer {
private:
  CompilerInstance &ci;
  SourceManager &sm;
  std::ostream *out;
  std::map<std::string, FileInfo *> relmap;
  LangOptions &features;
  DiagnosticConsumer *inner;

  FileInfo *getFileInfo(const std::string &filename) {
    std::map<std::string, FileInfo *>::iterator it;
    it = relmap.find(filename);
    if (it == relmap.end()) {
      // We haven't seen this file before. We need to make the FileInfo
      // structure information ourselves
      const char *real = realpath(filename.c_str(), NULL);
      std::string realstr(real ? real : filename.c_str());
      it = relmap.find(realstr);
      if (it == relmap.end()) {
        // Still didn't find it. Make the FileInfo structure
        FileInfo *info = new FileInfo(realstr);
        it = relmap.insert(make_pair(realstr, info)).first;
      }
      it = relmap.insert(make_pair(filename, it->second)).first;
    }
    return it->second;
  }
  FileInfo *getFileInfo(const char *filename) {
    std::string filenamestr(filename);
    return getFileInfo(filenamestr);
  }
public:
  IndexConsumer(CompilerInstance &ci) :
    ci(ci), sm(ci.getSourceManager()), features(ci.getLangOpts()),
      m_currentFunction(NULL) {
    inner = ci.getDiagnostics().takeClient();
    ci.getDiagnostics().setClient(this, false);
    ci.getPreprocessor().addPPCallbacks(new PreprocThunk(this));
  }

  virtual DiagnosticConsumer *clone(DiagnosticsEngine &Diags) const {
    return new IndexConsumer(ci);

  }

  // Helpers for processing declarations
  // Should we ignore this location?
  bool interestingLocation(SourceLocation loc) {
    // If we don't have a valid location... it's probably not interesting.
    if (loc.isInvalid())
      return false;
    // I'm not sure this is the best, since it's affected by #line and #file
    // et al. On the other hand, if I just do spelling, I get really wrong
    // values for locations in macros, especially when ## is involved.
    std::string filename = sm.getPresumedLoc(loc).getFilename();
    // Invalid locations and built-ins: not interesting at all
    if (filename[0] == '<')
      return false;

    // Get the real filename
    FileInfo *f = getFileInfo(filename);
    return f->interesting;
  }

  std::string locationToString(SourceLocation loc) {
    PresumedLoc fixed = sm.getPresumedLoc(loc);
    std::string buffer = getFileInfo(fixed.getFilename())->realname;
    buffer += ":";
    buffer += fixed.getLine();
    buffer += ":";
    buffer += fixed.getColumn();
    return buffer;
  }

  // This is a wrapper around NamedDecl::getQualifiedNameAsString.
  // It produces more qualified output to distinguish several cases
  // which would otherwise be ambiguous.
  std::string getQualifiedName(const NamedDecl &d) {
    std::string ret;
    const DeclContext *ctx = d.getDeclContext();
    if (ctx->isFunctionOrMethod() && isa<NamedDecl>(ctx))
    {
      // This is a local variable.
      // d.getQualifiedNameAsString() will return the unqualifed name for this
      // but we want an actual qualified name so we can distinguish variables
      // with the same name but that are in different functions.
      ret = getQualifiedName(*cast<NamedDecl>(ctx)) + "::" + d.getNameAsString();
    }
    else
    {
      ret = d.getQualifiedNameAsString();
    }

    if (const FunctionDecl *fd = dyn_cast<FunctionDecl>(&d))
    {
      // This is a function.  getQualifiedNameAsString will return a string
      // like "ANamespace::AFunction".  To this we append the list of parameters
      // so that we can distinguish correctly between
      // void ANamespace::AFunction(int);
      //    and
      // void ANamespace::AFunction(float);
      ret += "(";
      const FunctionType *ft = fd->getType()->castAs<FunctionType>();
      if (const FunctionProtoType *fpt = dyn_cast<FunctionProtoType>(ft))
      {
        unsigned num_params = fd->getNumParams();
        for (unsigned i = 0; i < num_params; ++i) {
          if (i)
            ret += ", ";
          ret += fd->getParamDecl(i)->getType().getAsString();
        }

        if (fpt->isVariadic()) {
          if (num_params > 0)
            ret += ", ";
          ret += "...";
        }
      }
      ret += ")";
      if (ft->isConst())
        ret += " const";
    }

    // Make anonymous namespaces in separate files have separate names
#if CLANG_AT_LEAST(3, 5)
    const std::string anon_ns = "(anonymous namespace)";
#else
    const std::string anon_ns = "<anonymous namespace>";
#endif
    if (StringRef(ret).startswith(anon_ns))
    {
      const std::string &filename = ci.getFrontendOpts().Inputs[0].getFile().str();
      const std::string &realname = getFileInfo(filename)->realname;
      ret = "(" + ret.substr(1, anon_ns.size() - 2) + " in " + realname + ")" + ret.substr(anon_ns.size());
    }
    return ret;
  }

  void beginRecord(const char *name, SourceLocation loc) {
    FileInfo *f = getFileInfo(sm.getPresumedLoc(loc).getFilename());
    out = &f->info;
    *out << name;
  }
  void recordValue(const char *key, std::string value, bool needQuotes=false) {
    *out << "," << key << ",\"";
    int start = 0;
    if (needQuotes) {
      int quote = value.find('"');
      while (quote != -1) {
        // Need to repeat the "
        *out << value.substr(start, quote - start + 1) << "\"";
        start = quote + 1;
        quote = value.find('"', start);
      }
    }
    *out << value.substr(start) << "\"";
  }

  SourceLocation getFileLocation(SourceLocation loc) {
    while (loc.isValid() && loc.isMacroID())
    {
      if (!sm.isMacroArgExpansion(loc))
        return SourceLocation();
      loc = sm.getImmediateSpellingLoc(loc);
    }
    return loc;
  }

  void printExtent(SourceLocation begin, SourceLocation end) {
    if (!end.isValid())
      end = begin;
    begin = getFileLocation(begin);
    end   = getFileLocation(end);
    if (!begin.isValid() || !end.isValid())
      return;
    *out << ",extent," << sm.getDecomposedSpellingLoc(begin).second << ":" <<
      sm.getDecomposedSpellingLoc(
        Lexer::getLocForEndOfToken(end, 0, sm, features)).second;
  }

  Decl *getNonClosureDecl(Decl *d)
  {
    DeclContext *dc;
    for (dc = d->getDeclContext(); dc->isClosure(); dc = dc->getParent())
    {
    }
    return Decl::castFromDeclContext(dc);
  }

  void printScope(Decl *d) {
    Decl *ctxt = getNonClosureDecl(d);
    // Ignore namespace scopes, since it doesn't really help for source code
    // organization
    while (NamespaceDecl::classof(ctxt))
      ctxt = getNonClosureDecl(ctxt);
    // If the scope is an anonymous struct/class/enum/union, replace it with the
    // typedef name here as well.
    if (NamedDecl::classof(ctxt)) {
      NamedDecl *scope = static_cast<NamedDecl*>(ctxt);
      NamedDecl *namesource = scope;
      if (TagDecl::classof(scope)) {
        TagDecl *tag = static_cast<TagDecl*>(scope);
        NamedDecl *redecl = tag->getTypedefNameForAnonDecl();
        if (redecl)
          namesource = redecl;
      }
      recordValue("scopename", getQualifiedName(*namesource));
      recordValue("scopeloc", locationToString(scope->getLocation()));
    }
  }

  void declDef(const char *kind, const NamedDecl *decl, const NamedDecl *def, SourceLocation begin, SourceLocation end) {
    if (!def || def == decl)
      return;

    beginRecord("decldef", decl->getLocation());
    recordValue("qualname", getQualifiedName(*def));
    recordValue("declloc", locationToString(decl->getLocation()));
    recordValue("defloc", locationToString(def->getLocation()));
    if (kind)
      recordValue("kind", kind);
    printExtent(begin, end);
    *out << std::endl;
  }

  // All we need is to follow the final declaration.
  virtual void HandleTranslationUnit(ASTContext &ctx) {
    TraverseDecl(ctx.getTranslationUnitDecl());

    // Emit all files now
    std::map<std::string, FileInfo *>::iterator it;
    for (it = relmap.begin(); it != relmap.end(); it++) {
      if (!it->second->interesting)
        continue;
      // Look at how much code we have
      std::string content = it->second->info.str();
      if (content.length() == 0)
        continue;
      std::string filename = tmpdir;
      // Hashing the filename allows us to not worry about the file structure
      // not matching up.
      filename += hash(it->second->realname);
      filename += ".";
      filename += hash(content);
      filename += ".csv";

      // Okay, I want to use the standard library for I/O as much as possible,
      // but the C/C++ standard library does not have the feature of "open
      // succeeds only if it doesn't exist."
      int fd = open(filename.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0644);
      if (fd != -1) {
        write(fd, content.c_str(), content.length());
        close(fd);
      }
    }
  }

  // Tag declarations: class, struct, union, enum
  bool VisitTagDecl(TagDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;

    if (d->isThisDeclarationADefinition())
    {
      // Information we need for types: kind, fqname, simple name, location
      beginRecord("type", d->getLocation());
      // We get the name from the typedef if it's an anonymous declaration...
      NamedDecl *nd = d->getTypedefNameForAnonDecl();
      if (!nd)
        nd = d;
      recordValue("name", nd->getNameAsString());
      recordValue("qualname", getQualifiedName(*nd));
      recordValue("loc", locationToString(d->getLocation()));
      recordValue("kind", d->getKindName());
      printScope(d);
      // Linkify the name, not the `enum'
      printExtent(nd->getLocation(), nd->getLocation());
      *out << std::endl;
    }

    declDef("type", d, d->getDefinition(), d->getLocation(), d->getLocation());
    return true;
  }

  bool VisitCXXRecordDecl(CXXRecordDecl *d) {
    if (!interestingLocation(d->getLocation()) || !d->isCompleteDefinition())
      return true;

    // TagDecl already did decldef and type outputting; we just need impl
    for (CXXRecordDecl::base_class_iterator iter = d->bases_begin();
        iter != d->bases_end(); ++iter) {
      const Type *t = (*iter).getType().getTypePtr();
      NamedDecl *base = t->getAsCXXRecordDecl();
      // I don't know what's going on... just bail!
      if (!base)
        return true;
      beginRecord("impl", d->getLocation());
      recordValue("tcname", getQualifiedName(*d));
      recordValue("tcloc", locationToString(d->getLocation()));
      recordValue("tbname", getQualifiedName(*base));
      recordValue("tbloc", locationToString(base->getLocation()));
      *out << ",access,\"";
      switch ((*iter).getAccessSpecifierAsWritten()) {
      case AS_public: *out << "public"; break;
      case AS_protected: *out << "protected"; break;
      case AS_private: *out << "private"; break;
      case AS_none: break; // It's implied, but we can ignore that
      }
      if ((*iter).isVirtual())
        *out << " virtual";
      *out << "\"" << std::endl;
    }
    return true;
  }

  bool VisitFunctionDecl(FunctionDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;

    if (d->isThisDeclarationADefinition() ||
        d->isPure())  // until we have better support for pure-virtual functions
    {
      beginRecord("function", d->getLocation());
      recordValue("name", d->getNameAsString());
      recordValue("qualname", getQualifiedName(*d));
#if CLANG_AT_LEAST(3, 5)
      recordValue("type", d->getCallResultType().getAsString());
#else
      recordValue("type", d->getResultType().getAsString());
#endif
      std::string args("(");
      for (FunctionDecl::param_iterator it = d->param_begin();
          it != d->param_end(); it++) {
        args += ", ";
        args += (*it)->getType().getAsString();
      }
      if (d->getNumParams() > 0)
        args.erase(1, 2);
      args += ")";
      recordValue("args", args);
      recordValue("loc", locationToString(d->getLocation()));
      printScope(d);
      printExtent(d->getNameInfo().getBeginLoc(), d->getNameInfo().getEndLoc());
      // Print out overrides
      if (CXXMethodDecl::classof(d)) {
        CXXMethodDecl *cxxd = dyn_cast<CXXMethodDecl>(d);
        CXXMethodDecl::method_iterator iter = cxxd->begin_overridden_methods();
        if (iter) {
          recordValue("overridename", getQualifiedName(**iter));
          recordValue("overrideloc", locationToString((*iter)->getLocation()));
        }
      }
      *out << std::endl;
    }

    const FunctionDecl *def;
    if (d->isDefined(def))
      declDef("function", d, def, d->getNameInfo().getBeginLoc(), d->getNameInfo().getEndLoc());

    return true;
  }

  bool VisitCXXConstructorDecl(CXXConstructorDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;

    for (CXXConstructorDecl::init_const_iterator it = d->init_begin(), e = d->init_end(); it != e; ++it)
    {
      const CXXCtorInitializer *ci = *it;
      if (!ci->getMember() || !ci->isWritten())
        continue;
      printReference("variable", ci->getMember(), ci->getMemberLocation(), ci->getMemberLocation());
    }

    return true;
  }

  bool treatThisValueDeclAsADefinition(const ValueDecl *d)
  {
    const VarDecl *vd = dyn_cast<VarDecl>(d);
    if (!vd)
      return true;  // Things that are not VarDecls (FieldDecl, EnumConstantDecl) are always treated as definitions
    if (!vd->isThisDeclarationADefinition())
      return false;
    if (!isa<ParmVarDecl>(d))
      return true;
    // This var is part of a parameter list.  Only treat it as
    // a definition if a function is also being defined.
    const FunctionDecl *fd = dyn_cast<FunctionDecl>(d->getDeclContext());
    return fd && fd->isThisDeclarationADefinition();
  }

  std::string getValueForValueDecl(ValueDecl *d)
  {
    if (const VarDecl *vd = dyn_cast<VarDecl>(d)) {
      const Expr *init = vd->getAnyInitializer(vd);
      if (!isa<ParmVarDecl>(vd) &&
          init && !init->getType().isNull() && !init->isValueDependent() &&
          vd->getType().isConstQualified()) {
        if (const APValue *apv = vd->evaluateValue()) {
          std::string ret = apv->getAsString(vd->getASTContext(), vd->getType());
          // workaround for constant strings being shown as &"foo" or &"foo"[0]
          if (str_starts_with(ret, "&\""))
          {
            if (str_ends_with(ret, "\""))
              return ret.substr(1);
            if (str_ends_with(ret, "\"[0]"))
              return ret.substr(1, ret.length() - 4);
          }
          return ret;
        }
      }
    } else if (EnumConstantDecl *ecd = dyn_cast<EnumConstantDecl>(d)) {
      return ecd->getInitVal().toString(10);
    }
    return std::string();
  }

  void visitVariableDecl(ValueDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return;
    if (treatThisValueDeclAsADefinition(d))
    {
      beginRecord("variable", d->getLocation());
      recordValue("name", d->getNameAsString());
      recordValue("qualname", getQualifiedName(*d));
      recordValue("loc", locationToString(d->getLocation()));
      recordValue("type", d->getType().getAsString(), true);
      const std::string &value = getValueForValueDecl(d);
      if (!value.empty())
        recordValue("value", value, true);
      printScope(d);
      printExtent(d->getLocation(), d->getLocation());
      *out << std::endl;
    }
    if (VarDecl *vd = dyn_cast<VarDecl>(d)) {
      VarDecl *def = vd->getDefinition();
      if (!def) {
#if CLANG_AT_LEAST(3, 4)
        VarDecl *first = vd->getFirstDecl();
#else
        VarDecl *first = vd->getFirstDeclaration();
#endif
        VarDecl *lastTentative = 0;
        for (VarDecl::redecl_iterator i = first->redecls_begin(), e = first->redecls_end();
             i != e; ++i) {
          VarDecl::DefinitionKind kind = i->isThisDeclarationADefinition();
          if (kind == VarDecl::TentativeDefinition) {
            lastTentative = *i;
          }
        }
        def = lastTentative;
      }
      declDef("variable", vd, def, vd->getLocation(), vd->getLocation());
    }
  }

  bool VisitEnumConstantDecl(EnumConstantDecl *d) { visitVariableDecl(d); return true; }
  bool VisitFieldDecl(FieldDecl *d) { visitVariableDecl(d); return true; }
  bool VisitVarDecl(VarDecl *d) { visitVariableDecl(d); return true; }

  bool VisitTypedefNameDecl(TypedefNameDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;
    // If the underlying declaration is anonymous, the "real" name is already
    // this typedef, so don't record ourselves as a typedef.
    // XXX: this seems broken?
#if 0
    const Type *real = d->getUnderlyingType().getTypePtr();
    if (TagType::classof(real)) {DiagnosticsEngine &D = CI.getDiagnostics();
      unsigned DiagID = D.getCustomDiagID(DiagnosticsEngine::Error,
        "Output directory '" + output + "' does not exist");
      D.Report(DiagID);
      return false;
      if (static_cast<const TagType*>(real)->getDecl()->
          getTypedefNameForAnonDecl() == d)
        return true;
    }
#endif
    beginRecord("typedef", d->getLocation());
    recordValue("name", d->getNameAsString());
    recordValue("qualname", getQualifiedName(*d));
    recordValue("loc", locationToString(d->getLocation()));
//    recordValue("underlying", d->getUnderlyingType().getAsString());
    printScope(d);
    printExtent(d->getLocation(), d->getLocation());
    *out << std::endl;
    return true;
  }

  bool VisitTemplateTypeParmDecl(TemplateTypeParmDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;

    // This is not really a typedef but it is close enough and probably not
    // worth inventing a new record for.
    beginRecord("typedef", d->getLocation());
    recordValue("name", d->getNameAsString());
    recordValue("qualname", getQualifiedName(*d));
    recordValue("loc", locationToString(d->getLocation()));
    printScope(d);
    printExtent(d->getLocation(), d->getLocation());
    *out << std::endl;
    return true;
  }

  // Like "namespace foo;"
  bool VisitNamespaceDecl(NamespaceDecl *d)
  {
    if (!interestingLocation(d->getLocation()))
      return true;
    beginRecord("namespace", d->getLocation());
    recordValue("name", d->getNameAsString());
    recordValue("qualname", getQualifiedName(*d));
    recordValue("loc", locationToString(d->getLocation()));
    printExtent(d->getLocation(), d->getLocation());
    *out << std::endl;
    return true;
  }

  // Like "namespace bar = foo;"
  bool VisitNamespaceAliasDecl(NamespaceAliasDecl *d)
  {
    if (!interestingLocation(d->getLocation()))
      return true;

    beginRecord("namespace_alias", d->getAliasLoc());
    recordValue("name", d->getNameAsString());
    recordValue("qualname", getQualifiedName(*d));
    recordValue("loc", locationToString(d->getAliasLoc()));
    printExtent(d->getAliasLoc(), d->getAliasLoc());
    *out << std::endl;

    if (d->getQualifierLoc())
      visitNestedNameSpecifierLoc(d->getQualifierLoc());
    printReference("namespace", d->getAliasedNamespace(), d->getTargetNameLoc(), d->getTargetNameLoc());
    return true;
  }

  // Like "using namespace std;"
  bool VisitUsingDirectiveDecl(UsingDirectiveDecl *d)
  {
    if (!interestingLocation(d->getLocation()))
      return true;
    if (d->getQualifierLoc())
      visitNestedNameSpecifierLoc(d->getQualifierLoc());
    printReference("namespace", d->getNominatedNamespace(), d->getIdentLocation(), d->getIdentLocation());
    return true;
  }

  // Like "using std::string;"
  bool VisitUsingDecl(UsingDecl *d)
  {
    if (!interestingLocation(d->getLocation()))
      return true;
    if (d->getQualifierLoc())
      visitNestedNameSpecifierLoc(d->getQualifierLoc());
    // The part of the name after the last '::' is hard to deal with
    // since it may refer to more than one thing.  For now it is unhandled.
    return true;
  }

  bool VisitDecl(Decl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;
#ifdef DEBUG
    if (!TagDecl::classof(d) && !NamespaceDecl::classof(d) &&
        !FunctionDecl::classof(d) && !FieldDecl::classof(d) &&
        !VarDecl::classof(d) && !TypedefNameDecl::classof(d) &&
        !EnumConstantDecl::classof(d) && !AccessSpecDecl::classof(d) &&
        !LinkageSpecDecl::classof(d) && !NamespaceAliasDecl::classof(d) &&
        !UsingDirectiveDecl::classof(d) && !UsingDecl::classof(d))
      printf("Unprocessed kind %s\n", d->getDeclKindName());
#endif
    return true;
  }

  // Expressions!
  void printReference(const char *kind, NamedDecl *d, SourceLocation refLoc, SourceLocation end) {
    if (!interestingLocation(d->getLocation()) || !interestingLocation(refLoc))
      return;
    beginRecord("ref", refLoc);
    recordValue("declloc", locationToString(d->getLocation()));
    recordValue("loc", locationToString(refLoc));
    if (kind)
      recordValue("kind", kind);
    printExtent(refLoc, end);
    *out << std::endl;
  }
  const char *kindForDecl(const Decl *d)
  {
    if (isa<FunctionDecl>(d))
      return "function";
    if (isa<EnumConstantDecl>(d) || isa<VarDecl>(d) || isa<FieldDecl>(d))
      return "variable";
    return NULL;   // unhandled for now
  }
  bool VisitMemberExpr(MemberExpr *e) {
    printReference(kindForDecl(e->getMemberDecl()),
                   e->getMemberDecl(),
                   e->getExprLoc(),
                   e->getSourceRange().getEnd());
    return true;
  }
  bool VisitDeclRefExpr(DeclRefExpr *e) {
    if (e->hasQualifier())
      visitNestedNameSpecifierLoc(e->getQualifierLoc());
    SourceLocation start = e->getLocation();
    SourceLocation end = e->getNameInfo().getEndLoc();
    if (FunctionDecl *fd = dyn_cast<FunctionDecl>(e->getDecl())) {
      /* We want to avoid overlapping refs for operator() or operator[]
         at least until we have better support for overlapping refs.
         Since the arguments can themselves be references we limit the
         reference for the method itself to just the initial token,
         not the entire range between '(' and ')' (or '[' and ']'). */
      if (fd->getOverloadedOperator() == OO_Call ||     // operator()
          fd->getOverloadedOperator() == OO_Subscript)  // operator[]
       end = start;
    }
    printReference(kindForDecl(e->getDecl()),
                   e->getDecl(),
                   start,
                   end);
    return true;
  }

  bool VisitCallExpr(CallExpr *e) {
    if (!interestingLocation(e->getLocStart()))
      return true;

    Decl *callee = e->getCalleeDecl();
    if (!callee || !interestingLocation(callee->getLocation()) ||
        !NamedDecl::classof(callee))
      return true;

    // Fun facts about call exprs:
    // 1. callee isn't necessarily a function. Think function pointers.
    // 2. We might not be in a function. Think global function decls
    // 3. Virtual functions need not be called virtually!
    beginRecord("call", e->getLocStart());
    if (m_currentFunction) {
      recordValue("callername", getQualifiedName(*m_currentFunction));
      recordValue("callerloc", locationToString(m_currentFunction->getLocation()));
    }
    recordValue("calleename", getQualifiedName(*dyn_cast<NamedDecl>(callee)));
    recordValue("calleeloc", locationToString(callee->getLocation()));
    // Determine the type of call
    const char *type = "static";
    if (CXXMethodDecl::classof(callee)) {
      CXXMethodDecl *cxxcallee = dyn_cast<CXXMethodDecl>(callee);
      if (cxxcallee->isVirtual()) {
        // If it's a virtual function, we need the MemberExpr to be unqualified
        if (!MemberExpr::classof(e->getCallee()) ||
            !dyn_cast<MemberExpr>(e->getCallee())->hasQualifier())
          type = "virtual";
      }
    } else if (!FunctionDecl::classof(callee)) {
      // Assume not a function -> function pointer of some type.
      type = "funcptr";
    }
    recordValue("calltype", type);
    *out << std::endl;
    return true;
  }

  bool VisitCXXConstructExpr(CXXConstructExpr *e) {
    if (!interestingLocation(e->getLocStart()))
      return true;

    CXXConstructorDecl *callee = e->getConstructor();
    if (!callee || !interestingLocation(callee->getLocation()) ||
        !NamedDecl::classof(callee))
      return true;

    // Fun facts about call exprs:
    // 1. callee isn't necessarily a function. Think function pointers.
    // 2. We might not be in a function. Think global function decls
    // 3. Virtual functions need not be called virtually!
    beginRecord("call", e->getLocStart());
    if (m_currentFunction) {
      recordValue("callername", getQualifiedName(*m_currentFunction));
      recordValue("callerloc", locationToString(m_currentFunction->getLocation()));
    }
    recordValue("calleename", getQualifiedName(*dyn_cast<NamedDecl>(callee)));
    recordValue("calleeloc", locationToString(callee->getLocation()));

    // There are no virtual constructors in C++:
    recordValue("calltype", "static");

    *out << std::endl;
    return true;
  }

  // For binding stuff inside the directory, we need to find the containing
  // function. Unfortunately, there is no way to do this in clang, so we have
  // to maintain the function stack ourselves. Why is it a stack? Consider:
  // void foo() { class A { A() { } }; } <-- nested function
  FunctionDecl *m_currentFunction;
  bool TraverseDecl(Decl *d) {
    FunctionDecl *parent = m_currentFunction;
    if (d && FunctionDecl::classof(d)) {
      m_currentFunction = dyn_cast<FunctionDecl>(d);
    }
    RecursiveASTVisitor<IndexConsumer>::TraverseDecl(d);
    m_currentFunction = parent;
    return true;
  }

  // Type locators
  bool VisitTagTypeLoc(TagTypeLoc l) {
    if (!interestingLocation(l.getBeginLoc()))
      return true;

    printReference("type", l.getDecl(), l.getBeginLoc(), l.getEndLoc());
    return true;
  }

  bool VisitTypedefTypeLoc(TypedefTypeLoc l) {
    if (!interestingLocation(l.getBeginLoc()))
      return true;

    printReference("typedef", l.getTypedefNameDecl(), l.getBeginLoc(), l.getEndLoc());
    return true;
  }

  bool VisitElaboratedTypeLoc(ElaboratedTypeLoc l) {
    if (!interestingLocation(l.getBeginLoc()))
      return true;

    if (l.getQualifierLoc())
      visitNestedNameSpecifierLoc(l.getQualifierLoc());
    return true;
  }

  bool VisitInjectedClassNameTypeLoc(InjectedClassNameTypeLoc l) {
    if (!interestingLocation(l.getBeginLoc()))
      return true;

    printReference("type", l.getDecl(), l.getBeginLoc(), l.getEndLoc());
    return true;
  }

  bool VisitTemplateSpecializationTypeLoc(TemplateSpecializationTypeLoc l) {
    if (!interestingLocation(l.getBeginLoc()))
      return true;

    TemplateDecl *td = l.getTypePtr()->getTemplateName().getAsTemplateDecl();
    if (ClassTemplateDecl *d = dyn_cast<ClassTemplateDecl>(td))
      printReference("type", d, l.getTemplateNameLoc(), l.getTemplateNameLoc());

    return true;
  }

  bool VisitTemplateTypeParmTypeLoc(TemplateTypeParmTypeLoc l) {
    if (!interestingLocation(l.getBeginLoc()))
      return true;

    printReference("typedef", l.getDecl(), l.getBeginLoc(), l.getEndLoc());
    return true;
  }

  SourceLocation removeTrailingColonColon(SourceLocation begin, SourceLocation end)
  {
    if (!end.isValid())
      return end;

    SmallVector<char, 32> buffer;
    if (Lexer::getSpelling(end, buffer, sm, features) != "::")
      return end;

    SourceLocation prev;
    for (SourceLocation loc = begin;
         loc.isValid() && loc != end && loc != prev;
         loc = Lexer::getLocForEndOfToken(loc, 0, sm, features))
    {
      prev = loc;
    }

    return prev.isValid() ? prev : end;
  }

  void visitNestedNameSpecifierLoc(NestedNameSpecifierLoc l)
  {
    if (!interestingLocation(l.getBeginLoc()))
      return;

    if (l.getPrefix())
      visitNestedNameSpecifierLoc(l.getPrefix());

    SourceLocation begin = l.getLocalBeginLoc(), end = l.getLocalEndLoc();
    // we don't want the "::" to be part of the link.
    end = removeTrailingColonColon(begin, end);

    NestedNameSpecifier *nss = l.getNestedNameSpecifier();
    if (nss->getKind() == NestedNameSpecifier::Namespace)
      printReference("namespace", nss->getAsNamespace(), begin, end);
    else if (nss->getKind() == NestedNameSpecifier::NamespaceAlias)
      printReference("namespace_alias", nss->getAsNamespaceAlias(), begin, end);
  }

  // Warnings!
  SourceLocation getWarningExtentLocation(SourceLocation loc) {
    while (loc.isMacroID()) {
      if (sm.isMacroArgExpansion(loc))
        loc = sm.getImmediateSpellingLoc(loc);
      else
        loc = sm.getImmediateExpansionRange(loc).first;
    }
    return loc;
  }

  virtual void HandleDiagnostic(DiagnosticsEngine::Level level,
      const Diagnostic &info) {
    DiagnosticConsumer::HandleDiagnostic(level, info);
    inner->HandleDiagnostic(level, info);
    if (level != DiagnosticsEngine::Warning ||
        !interestingLocation(info.getLocation()))
      return;

    llvm::SmallString<100> message;
    info.FormatDiagnostic(message);

    beginRecord("warning", info.getLocation());
    recordValue("loc", locationToString(info.getLocation()));
    recordValue("msg", message.c_str(), true);
    StringRef opt = DiagnosticIDs::getWarningOptionForDiag(info.getID());
    if (!opt.empty())
      recordValue("opt", ("-W" + opt).str());
    if (info.getNumRanges() > 0) {
      const CharSourceRange &range = info.getRange(0);
      printExtent(getWarningExtentLocation(range.getBegin()),
                  getWarningExtentLocation(range.getEnd()));
    } else {
      SourceLocation loc = getWarningExtentLocation(info.getLocation());
      printExtent(loc, loc);
    }
    *out << std::endl;
  }

  // Macros!
  virtual void MacroDefined(const Token &MacroNameTok, const MacroInfo *MI) {
    if (MI->isBuiltinMacro()) return;
    if (!interestingLocation(MI->getDefinitionLoc())) return;

    // Yep, we're tokenizing this ourselves. Fun!
    SourceLocation nameStart = MI->getDefinitionLoc();
    SourceLocation textEnd = MI->getDefinitionEndLoc();
    unsigned int length =
      sm.getFileOffset(Lexer::getLocForEndOfToken(textEnd, 0, sm, features)) -
      sm.getFileOffset(nameStart);
    const char *contents = sm.getCharacterData(nameStart);
    unsigned int nameLen = MacroNameTok.getIdentifierInfo()->getLength();
    unsigned int argsStart = 0, argsEnd = 0, defnStart;

    // Grab the macro arguments if it has some
    if (nameLen < length && contents[nameLen] == '(') {
      argsStart = nameLen;
      for (argsEnd = nameLen + 1; argsEnd < length; argsEnd++)
        if (contents[argsEnd] == ')') {
          argsEnd++;
          break;
        }
      defnStart = argsEnd;
    } else {
      defnStart = nameLen;
    }
    // Find the first non-whitespace character for the definition.
    for (; defnStart < length; defnStart++) {
      switch (contents[defnStart]) {
        case ' ': case '\t': case '\v': case '\r': case '\n': case '\f':
          continue;
      }
      break;
    }
    beginRecord("macro", nameStart);
    recordValue("loc", locationToString(nameStart));
    recordValue("name", std::string(contents, nameLen));
    if (argsStart > 0)
      recordValue("args", std::string(contents + argsStart,
        argsEnd - argsStart), true);
    if (defnStart < length) {
      std::string text =  std::string(contents + defnStart,
        length - defnStart);
      // FIXME: handle non-ASCII characters better
      for (size_t i = 0; i < text.size(); ++i)
        if ((text[i] < ' ' || text[i] >= 0x7F) && text[i] != '\t' && text[i] != '\n')
          text[i] = '?';
      recordValue("text", text, true);
    }
    printExtent(nameStart, nameStart);
    *out << std::endl;
  }

  void printMacroReference(const Token &tok, const MacroInfo *MI) {
    if (!interestingLocation(tok.getLocation())) return;

    IdentifierInfo *ii = tok.getIdentifierInfo();
    if (!MI)
      MI = ci.getPreprocessor().getMacroInfo(ii);
    if (!MI)
      return;
    if (MI->isBuiltinMacro()) return;

    SourceLocation macroLoc = MI->getDefinitionLoc();
    SourceLocation refLoc = tok.getLocation();
    beginRecord("ref", refLoc);
    recordValue("name", std::string(ii->getNameStart(), ii->getLength()));
    recordValue("declloc", locationToString(macroLoc));
    recordValue("loc", locationToString(refLoc));
    recordValue("kind", "macro");
    printExtent(refLoc, refLoc);
    *out << std::endl;
  }

  virtual void MacroExpands(const Token &tok, const MacroInfo *MI, SourceRange Range) {
    printMacroReference(tok, MI);
  }
  virtual void MacroUndefined(const Token &tok, const MacroInfo *MI) {
    printMacroReference(tok, MI);
  }
  virtual void Defined(const Token &tok, const MacroInfo *MI) {
    printMacroReference(tok, MI);
  }
  virtual void Ifdef(SourceLocation loc, const Token &tok, const MacroInfo *MI) {
    printMacroReference(tok, MI);
  }
  virtual void Ifndef(SourceLocation loc, const Token &tok, const MacroInfo *MI) {
    printMacroReference(tok, MI);
  }

  virtual void InclusionDirective(
      SourceLocation hashLoc,
      const Token &includeTok,
      StringRef fileName,
      bool isAngled,
      CharSourceRange filenameRange,
      const FileEntry *file,
      StringRef searchPath,
      StringRef relativePath,
      const Module *imported) {
    PresumedLoc presumedHashLoc;
    FileInfo *target, *source;
    SourceLocation targetBegin, targetEnd;

    if (!interestingLocation(hashLoc) ||
        filenameRange.isInvalid() ||
        (presumedHashLoc = sm.getPresumedLoc(hashLoc)).isInvalid() ||

        // Don't record inclusions of files that are outside the source tree,
        // like stdlibs. file is NULL if an #include can't be resolved, like if
        // you include a nonexistent file.
        !file ||

        !(target = getFileInfo(file->getName()))->interesting ||

        // TODO: Come up with some kind of reasonable extent for macro-based
        // includes, like #include FOO_MACRO.
        (targetBegin = filenameRange.getBegin()).isMacroID() ||
        (targetEnd = filenameRange.getEnd()).isMacroID() ||

        // TODO: Support generated files once we run the trigram indexer over
        // them. For now, we skip them.
        !(source = getFileInfo(presumedHashLoc.getFilename()))->realname.compare(0, GENERATED.size(), GENERATED) ||
        !(target->realname.compare(0, GENERATED.size(), GENERATED)))
      return;

    beginRecord("include", hashLoc);
    recordValue("source_path", source->realname);
    recordValue("target_path", target->realname);
    printExtent(targetBegin, targetEnd);
    *out << std::endl;
  }

};

#if CLANG_AT_LEAST(3, 3)
  void PreprocThunk::MacroDefined(const Token &tok, const MacroDirective *md) {
    real->MacroDefined(tok, md->getMacroInfo());
  }
  void PreprocThunk::MacroExpands(const Token &tok, const MacroDirective *md, SourceRange range, const MacroArgs *ma) {
    real->MacroExpands(tok, md->getMacroInfo(), range);
  }
  void PreprocThunk::MacroUndefined(const Token &tok, const MacroDirective *md) {
    real->MacroUndefined(tok, md->getMacroInfo());
  }
#if CLANG_AT_LEAST(3, 4)
  void PreprocThunk::Defined(const Token &tok, const MacroDirective *md, SourceRange) {
#else
  void PreprocThunk::Defined(const Token &tok, const MacroDirective *md) {
#endif
    real->Defined(tok, md->getMacroInfo());
  }
  void PreprocThunk::Ifdef(SourceLocation loc, const Token &tok, const MacroDirective *md) {
    real->Ifdef(loc, tok, md->getMacroInfo());
  }
  void PreprocThunk::Ifndef(SourceLocation loc, const Token &tok, const MacroDirective *md) {
    real->Ifndef(loc, tok, md->getMacroInfo());
  }
#else
  void PreprocThunk::MacroDefined(const Token &tok, const MacroInfo *MI) {
    real->MacroDefined(tok, MI);
  }
  void PreprocThunk::MacroExpands(const Token &tok, const MacroInfo *MI, SourceRange Range) {
    real->MacroExpands(tok, MI, Range);
  }
  void PreprocThunk::MacroUndefined(const Token &tok, const MacroInfo *MI) {
    real->MacroUndefined(tok, MI);
  }
  void PreprocThunk::Defined(const Token &tok) {
    real->Defined(tok, NULL);
  }
  void PreprocThunk::Ifdef(SourceLocation loc, const Token &tok) {
    real->Ifdef(loc, tok, NULL);
  }
  void PreprocThunk::Ifndef(SourceLocation loc, const Token &tok) {
    real->Ifndef(loc, tok, NULL);
  }
#endif
void PreprocThunk::InclusionDirective(  // same in 3.2 and 3.3
    SourceLocation hashLoc,
    const Token &includeTok,
    StringRef fileName,
    bool isAngled,
    CharSourceRange filenameRange,
    const FileEntry *file,
    StringRef searchPath,
    StringRef relativePath,
    const Module *imported) {
  real->InclusionDirective(hashLoc, includeTok, fileName, isAngled, filenameRange, file, searchPath, relativePath, imported);
}

class DXRIndexAction : public PluginASTAction {
protected:
  ASTConsumer *CreateASTConsumer(CompilerInstance &CI, llvm::StringRef f) {
    return new IndexConsumer(CI);
  }

  bool ParseArgs(const CompilerInstance &CI,
                 const std::vector<std::string>& args) {
    if (args.size() != 1) {
      DiagnosticsEngine &D = CI.getDiagnostics();
      unsigned DiagID = D.getCustomDiagID(DiagnosticsEngine::Error,
        "Need an argument for the source directory");
      D.Report(DiagID);
      return false;
    }
    // Load our directories
    char *abs_src = realpath(args[0].c_str(), NULL);
    if (!abs_src) {
      DiagnosticsEngine &D = CI.getDiagnostics();
      unsigned DiagID = D.getCustomDiagID(DiagnosticsEngine::Error,
        "Source directory '%0' does not exist");
      D.Report(DiagID) << args[0];
      return false;
    }
    srcdir = abs_src;
    const char *env = getenv("DXR_CXX_CLANG_OBJECT_FOLDER");
    if (env)
      output = env;
    else
      output = srcdir;
    char *abs_output = realpath(output.c_str(), NULL);
    if (!abs_output) {
      DiagnosticsEngine &D = CI.getDiagnostics();
      unsigned DiagID = D.getCustomDiagID(DiagnosticsEngine::Error,
        "Output directory '%0' does not exist");
      D.Report(DiagID) << output;
      return false;
    }
    output = realpath(output.c_str(), NULL);
    output += "/";

    const char* tmp = getenv("DXR_CXX_CLANG_TEMP_FOLDER");
    if(tmp){
      tmpdir = tmp;
    }else
      tmpdir = output;

    char* abs_tmpdir = realpath(tmpdir.c_str(), NULL);
    if(!abs_tmpdir){
      DiagnosticsEngine &D = CI.getDiagnostics();
      unsigned DiagID = D.getCustomDiagID(DiagnosticsEngine::Error,
        "Temporary directory '%0' does not exist");
      D.Report(DiagID) << tmpdir;
      return false;
    }
    tmpdir = realpath(tmpdir.c_str(), NULL);
    tmpdir += "/";

    return true;
  }
  void PrintHelp(llvm::raw_ostream& ros) {
    ros << "Help for PrintFunctionNames plugin goes here\n";
  }

};

}

static FrontendPluginRegistry::Add<DXRIndexAction>
X("dxr-index", "create the dxr index database");
