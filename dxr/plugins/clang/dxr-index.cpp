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
#include <memory>
#include <sstream>
#include <stdio.h>
#include <stdlib.h>

// Needed for sha1 hacks
#include <fcntl.h>
#include <unistd.h>
#include "sha1.h"

#define CLANG_AT_LEAST(major, minor) \
  (CLANG_VERSION_MAJOR > (major) || \
   (CLANG_VERSION_MAJOR == (major) && CLANG_VERSION_MINOR >= (minor)))

using namespace clang;

namespace {

const std::string GENERATED("--GENERATED--/");

// Curse whoever didn't do this.
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
  return s.size() >= suffix.size() &&
    s.compare(s.size() - suffix.size(), suffix.size(), suffix) == 0;
}

// BEWARE: use only as a temporary
const char *hash(std::string &str) {
  static unsigned char rawhash[20];
  static char hashstr[41];
  sha1::calc(str.c_str(), str.size(), rawhash);
  sha1::toHexString(rawhash, hashstr);
  return hashstr;
}

struct FileInfo {
  FileInfo(std::string &rname) : realname(rname) {
    interesting = rname.compare(0, srcdir.length(), srcdir) == 0;
    if (interesting) {
      // Remove the trailing `/' as well.
      realname.erase(0, srcdir.length());
    } else if (rname.compare(0, output.length(), output) == 0) {
      // We're in the output directory, so we are probably a generated header.
      // We use the escape character to indicate the objdir nature.
      // Note that output also has the `/' already placed.
      interesting = true;
      realname.replace(0, output.length(), GENERATED);
    }
  }
  std::string realname;
  std::ostringstream info;
  bool interesting;
  static std::string srcdir;  // the project source directory
  static std::string output;  // the project build directory
};
typedef std::shared_ptr<FileInfo> FileInfoPtr;

class IndexConsumer;

// PreprocThunk handles our consumption of the preprocessing stage of the
// compilation.
// Functionally, we just pass off the work to our IndexConsumer object.
class PreprocThunk : public PPCallbacks {
  IndexConsumer *real;
public:
  PreprocThunk(IndexConsumer *c) : real(c) {}
#if CLANG_AT_LEAST(3, 3)
  void MacroDefined(const Token &tok, const MacroDirective *md) override;
  #if CLANG_AT_LEAST(3, 7)
    void MacroExpands(const Token &tok, const MacroDefinition &md,
                      SourceRange range, const MacroArgs *ma) override;
    #if CLANG_AT_LEAST(5, 0)
    void MacroUndefined(const Token &tok, const MacroDefinition &md,
                        const MacroDirective *Undef) override;
    #else
    void MacroUndefined(const Token &tok, const MacroDefinition &md) override;
    #endif
    void Ifdef(SourceLocation loc, const Token &tok,
               const MacroDefinition &md) override;
    void Ifndef(SourceLocation loc, const Token &tok,
                const MacroDefinition &md) override;
  #else
    void MacroExpands(const Token &tok, const MacroDirective *md,
                      SourceRange range, const MacroArgs *ma) override;
    void MacroUndefined(const Token &tok, const MacroDirective *md) override;
    void Ifdef(SourceLocation loc, const Token &tok,
               const MacroDirective *md) override;
    void Ifndef(SourceLocation loc, const Token &tok,
                const MacroDirective *md) override;
  #endif
  #if CLANG_AT_LEAST(3, 7)
    void Defined(const Token &tok, const MacroDefinition &md,
                 SourceRange range) override;
  #elif CLANG_AT_LEAST(3, 4)
    void Defined(const Token &tok, const MacroDirective *md,
                 SourceRange range) override;
  #else
    void Defined(const Token &tok, const MacroDirective *md) override;
  #endif
#else  // clang < 3.3
  void MacroDefined(const Token &MacroNameTok, const MacroInfo *MI) override;
  void MacroExpands(const Token &MacroNameTok, const MacroInfo *MI,
                    SourceRange Range) override;
  void MacroUndefined(const Token &tok, const MacroInfo *MI) override;
  void Defined(const Token &tok) override;
  void Ifdef(SourceLocation loc, const Token &tok) override;
  void Ifndef(SourceLocation loc, const Token &tok) override;
#endif
#if CLANG_AT_LEAST(7, 0)
  void InclusionDirective(
      SourceLocation hashLoc,
      const Token &includeTok,
      StringRef fileName,
      bool isAngled,
      CharSourceRange filenameRange,
      const FileEntry *file,
      StringRef searchPath,
      StringRef relativePath,
      const Module *imported,
      SrcMgr::CharacteristicKind FileType) override;
#else
  void InclusionDirective(
      SourceLocation hashLoc,
      const Token &includeTok,
      StringRef fileName,
      bool isAngled,
      CharSourceRange filenameRange,
      const FileEntry *file,
      StringRef searchPath,
      StringRef relativePath,
      const Module *imported) override;
#endif
};

// IndexConsumer is our primary AST consumer.
class IndexConsumer : public ASTConsumer,
                      public RecursiveASTVisitor<IndexConsumer>,
                      public DiagnosticConsumer {
private:
  CompilerInstance &ci;
  SourceManager &sm;
  std::ostream *out;
  std::map<std::string, FileInfoPtr> relmap;
  // Map the SourceLocation of a macro to the text of the macro def.
  std::map<SourceLocation, std::string> macromap;
  LangOptions &features;
#if CLANG_AT_LEAST(3, 6)
  std::unique_ptr<DiagnosticConsumer> inner;
#else
  DiagnosticConsumer *inner;
#endif
  static std::string tmpdir;  // Place to save all the csv files to
  PrintingPolicy printPolicy;

  const FileInfoPtr &getFileInfo(const std::string &filename) {
    std::map<std::string, FileInfoPtr>::iterator it;
    it = relmap.find(filename);
    if (it == relmap.end()) {
      // Check if we have this file stored under a canonicalized key.
      char *real = realpath(filename.c_str(), nullptr);
      std::string realstr(real ? real : filename.c_str());
      free(real);
      it = relmap.find(realstr);
      if (it == relmap.end()) {
        // We haven't seen this file before. We need to make the FileInfo
        // structure information ourselves.
        it = relmap.insert(make_pair(realstr,
                                     std::make_shared<FileInfo>(realstr))).first;
      }
      // Note that the map values for the filename and realstr keys will both
      // point to the same FileInfo object, which is what we want.
      it = relmap.insert(make_pair(filename, it->second)).first;
    }
    return it->second;
  }
  const FileInfoPtr &getFileInfo(const char *filename) {
    std::string filenamestr(filename);
    return getFileInfo(filenamestr);
  }
public:
  IndexConsumer(CompilerInstance &ci)
    : ci(ci), sm(ci.getSourceManager()), features(ci.getLangOpts()),
      printPolicy(features) {

    inner = ci.getDiagnostics().takeClient();
    ci.getDiagnostics().setClient(this, false);
#if CLANG_AT_LEAST(3, 6)
    ci.getPreprocessor().addPPCallbacks(std::unique_ptr<PPCallbacks>(new PreprocThunk(this)));
#else
    ci.getPreprocessor().addPPCallbacks(new PreprocThunk(this));
#endif
    // Print "bool" instead of "_Bool" when we print types.
    printPolicy.Bool = true;
    // Print just 'mytype' instead of 'class mytype' or 'enum mytype' etc.;
    // the tag doesn't help us and probably makes it harder to craft
    // handwritten queries.
    printPolicy.SuppressTagKeyword = true;
  }

  ~IndexConsumer() {
#if CLANG_AT_LEAST(3, 6)
    ci.getDiagnostics().setClient(inner.release());
#else
    ci.getDiagnostics().setClient(inner);
#endif
  }

#if CLANG_AT_LEAST(3, 3)
  // `clone` was removed from the DiagnosticConsumer interface in version 3.3,
  // so this can all be deleted once we're no longer supporting 3.2.
#else
  DiagnosticConsumer *clone(DiagnosticsEngine &Diags) const override {
    return new IndexConsumer(ci);
  }
#endif

  static void setTmpDir(const std::string& dir) { tmpdir = dir; }

  //// Helpers for processing declarations

  // Should we ignore this location?
  bool interestingLocation(SourceLocation loc) {
    // If we don't have a valid location... it's probably not interesting.
    if (loc.isInvalid())
      return false;
    // I'm not sure this is the best, since it's affected by #line and #file
    // et al. On the other hand, if I just do spelling, I get really wrong
    // values for locations in macros, especially when ## is involved.
    // TODO: So yeah, maybe use sm.getFilename(loc) instead.
    std::string filename = sm.getPresumedLoc(loc).getFilename();
    // Invalid locations and built-ins: not interesting at all
    if (filename[0] == '<')
      return false;

    // Get the real filename
    const FileInfoPtr &f = getFileInfo(filename);
    return f->interesting;
  }

  // Return a source location's file path, line, and column, or '' if the
  // location is invalid.
  std::string locationToString(SourceLocation loc) {
    std::string buffer;
    bool isInvalid;
    // Since we're dealing with only expansion locations here, we should be
    // guaranteed to stay within the same file as "out" points to.
    unsigned column = sm.getExpansionColumnNumber(loc, &isInvalid);

    if (!isInvalid) {
      unsigned line = sm.getExpansionLineNumber(loc, &isInvalid);
      if (!isInvalid) {
        // getFilename seems to want a SpellingLoc. I may be disappointing
        // it. I'm not sure what it will do if it's disappointed.
        buffer = getFileInfo(sm.getFilename(loc).str())->realname;
        buffer += ":";
        buffer += line;
        buffer += ":";
        buffer += column - 1;  // Make 0-based.
      }
    }
    return buffer;
  }

  // Return the location right after the token at `loc` finishes.
  SourceLocation afterToken(SourceLocation loc, const std::string& tokenHint = "") {
    // TODO: Would it be safe to just change this function to be
    //    return loc.getLocWithOffset(tokenHint.size());
    // in the cases where we already know the full name in the caller?
    // In the meantime we're only using tokenHint for its first character: the
    // lexer treats '~' as a token in some cases and not in others (due to the
    // ambiguity between whether '~X();' means destructor decl or one's
    // complement on the return of a function), so we help things along by just
    // always starting one after the '~'.
    if (tokenHint.size() > 1 && tokenHint[0] == '~')
      loc = loc.getLocWithOffset(1);
    // TODO: Perhaps, at callers, pass me begin if !end.isValid().
    return Lexer::getLocForEndOfToken(loc, 0, sm, features);
  }

  // Record the correct "locend" for name (when name is the name of a destructor
  // it works around some inconsistencies).
  void recordLocEndForName(const std::string& name,
                           SourceLocation beginLoc, SourceLocation endLoc) {
    // Some versions (or settings or whatever) of clang consider '~MyClass' to
    // be two tokens, others just one, so we just always let afterToken take
    // care of the '~' when there is one.
    if (name.size() > 1 && name[0] == '~')
      recordValue("locend", locationToString(afterToken(beginLoc, name)));
    else
      recordValue("locend", locationToString(afterToken(endLoc)));
  }

  // Given a declaration, get the name of the file containing the corresponding
  // definition or the name of the file containing the declaration if no
  // definition can be found.
  std::string getRealFilenameForDefinition(const NamedDecl &d) {
    const NamedDecl *decl = &d;

    if (const FunctionDecl *fd = dyn_cast<FunctionDecl>(decl)) {
      const FunctionDecl *def = 0;
      if (fd->isDefined(def))
        decl = def;
    }

    const std::string &filename = sm.getFilename(decl->getLocation());
    return getFileInfo(filename)->realname;
  }

  // This is a wrapper around NamedDecl::getQualifiedNameAsString.
  // It produces more qualified output to distinguish several cases
  // which would otherwise be ambiguous.
  std::string getQualifiedName(const NamedDecl &d) {
    std::string ret;
    const FunctionDecl *fd = nullptr;
    const DeclContext *ctx = d.getDeclContext();
    if (ctx->isFunctionOrMethod() && isa<NamedDecl>(ctx)) {
      // This is a local variable.
      // d.getQualifiedNameAsString() will return the unqualifed name for this
      // but we want an actual qualified name so we can distinguish variables
      // with the same name but that are in different functions.
      ret = getQualifiedName(*cast<NamedDecl>(ctx)) + "::" + d.getNameAsString();
    }
    else {
      if ((fd = dyn_cast<FunctionDecl>(&d))) {  // A function
        if (fd->isTemplateInstantiation()) {
          // Use the original template pattern, not the substituted concrete
          // types, for the qualname:
          fd = fd->getTemplateInstantiationPattern();
#if 0 // Activate this section to give most full (but no partial!) function
      // template specializations the same qualname as the base template.
        } else if (FunctionTemplateSpecializationInfo *ftsi =
                     fd->getTemplateSpecializationInfo()) {
          // This gives a function template and its full specializations the
          // same qualname.  Unfortunately I don't know how to do the same for
          // *partial* class template specializations, so for now the original
          // template and each partial specialization gets its own qualname.
          fd = ftsi->getTemplate()->getTemplatedDecl();
#endif
        }
        // Canonicalize the decl - otherwise you can get different qualnames
        // depending on the location of your decl (which would be bad).
        fd = fd->getCanonicalDecl();
        ret = fd->getQualifiedNameAsString();
      }
      else {
        ret = d.getQualifiedNameAsString();
      }
    }

    if (fd) {
      // This is a function.  getQualifiedNameAsString will return a string
      // like "ANamespace::AFunction".  To this we append the list of parameters
      // so that we can distinguish correctly between
      // void ANamespace::AFunction(int);
      //    and
      // void ANamespace::AFunction(float);
      ret += "(";
      const FunctionType *ft = fd->getType()->castAs<FunctionType>();
      if (const FunctionProtoType *fpt = dyn_cast<FunctionProtoType>(ft)) {
        unsigned num_params = fd->getNumParams();
        for (unsigned i = 0; i < num_params; ++i) {
          if (i)
            ret += ", ";
          ret += fd->getParamDecl(i)->getType().getAsString(printPolicy);
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

    // Make anonymous namespaces in separate files have separate names.
#if CLANG_AT_LEAST(3, 5)
    const std::string anon_ns = "(anonymous namespace)";
#else
    const std::string anon_ns = "<anonymous namespace>";
#endif
    if (StringRef(ret).startswith(anon_ns)) {
      const std::string &realname = getRealFilenameForDefinition(d);
      ret = "(" + ret.substr(1, anon_ns.size() - 2) + " in " + realname + ")" +
        ret.substr(anon_ns.size());
    } else if (d.getLinkageInternal() == InternalLinkage) {
      const std::string &realname = getRealFilenameForDefinition(d);
      ret = "(static in " + realname + ")::" + ret;
    }
    return ret;
  }

  // Switch the output pointer to a specific file's CSV, and write a line header
  // to it.
  void beginRecord(const char *name, SourceLocation loc) {
    // Only a PresumedLoc has a getFilename() method, unfortunately. We'd
    // rather have the expansion location than the presumed one, as we're not
    // interested in lies told by the #lines directive.
    StringRef filename = sm.getFilename(loc);
    const FileInfoPtr &f = getFileInfo(filename);
    out = &(f->info);
    *out << name;
  }

  void recordValue(const char *key, std::string value) {
    *out << "," << key << ",\"";
    int start = 0;
    int quote = value.find('"');
    while (quote != -1) {
      // Need to repeat the "
      *out << value.substr(start, quote - start + 1) << "\"";
      start = quote + 1;
      quote = value.find('"', start);
    }
    *out << value.substr(start) << "\"";
  }

  // If we're in a macro definition or even a stack of macros that all call
  // each other, walk up out that mess, back to the place that called the
  // first macro. This is useful for getting back to the actual place that
  // cites a variable that then gets passed to a macro.
  SourceLocation escapeMacros(SourceLocation loc) {
    while (loc.isValid() && loc.isMacroID()) {
      if (!sm.isMacroArgExpansion(loc))
        return SourceLocation();
      loc = sm.getImmediateSpellingLoc(loc);
    }
    return loc;
  }

  Decl *getNonClosureDecl(Decl *d) {
    DeclContext *dc;
    for (dc = d->getDeclContext(); dc->isClosure(); dc = dc->getParent())
      ;
    return Decl::castFromDeclContext(dc);
  }

  void printScope(Decl *d) {
    Decl *ctxt = getNonClosureDecl(d);
    // Ignore namespace scopes, since it doesn't really help for source code
    // organization.
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
      recordValue("scopename", namesource->getNameAsString());
      recordValue("scopequalname", getQualifiedName(*namesource));
    }
  }

  // vars, funcs, types, enums, classes, unions, etc.
  void declDef(const char *kind, const NamedDecl *decl, const NamedDecl *def,
               SourceLocation begin, SourceLocation end) {
    if (def == decl) {
      return;
    }

    beginRecord("decldef", decl->getLocation());  // Assuming this is an
                                                  // expansion location.
    std::string name = decl->getNameAsString();
    recordValue("name", name);
    recordValue("qualname", getQualifiedName(def ? *def : *decl));
    recordValue("loc", locationToString(decl->getLocation()));
    recordValue("locend",
                locationToString(afterToken(decl->getLocation(), name)));
    if (def)
      recordValue("defloc", locationToString(def->getLocation()));
    if (kind)
      recordValue("kind", kind);
    *out << std::endl;
  }

  //// AST processing overrides

  // All we need is to follow the final declaration.
  void HandleTranslationUnit(ASTContext &ctx) override {
    TraverseDecl(ctx.getTranslationUnitDecl());

    // Emit all files now
    std::map<std::string, FileInfoPtr>::iterator it;
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

    if (d->isThisDeclarationADefinition()) {
      SourceLocation begin;
      // Information we need for types: kind, fqname, simple name, location
      beginRecord("type", d->getLocation());
      // We get the name from the typedef if it's an anonymous declaration...
      NamedDecl *nd = d->getTypedefNameForAnonDecl();
      if (!nd)
        nd = d;
      recordValue("name", nd->getNameAsString());
      recordValue("qualname", getQualifiedName(*nd));
      recordValue("loc", locationToString(begin = d->getLocation()));
      recordValue("locend", locationToString(afterToken(begin)));
      recordValue("kind", d->getKindName());
      printScope(d);
      *out << std::endl;
    }

    declDef("type", d, d->getDefinition(),
            d->getLocation(), afterToken(d->getLocation()));
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
      if (!base)  // I don't know what's going on... just bail!
        return true;
      beginRecord("impl", d->getLocation());
      recordValue("name", d->getNameAsString());
      recordValue("qualname", getQualifiedName(*d));
      recordValue("basename", base->getNameAsString());
      recordValue("basequalname", getQualifiedName(*base));
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

    if (d->isThisDeclarationADefinition() || d->isPure()) {
      SourceLocation functionLocation = d->getLocation();
      beginRecord("function", functionLocation);
      std::string functionName = d->getNameAsString();
      recordValue("name", functionName);
      std::string functionQualName = getQualifiedName(*d);
      recordValue("qualname", functionQualName);
#if CLANG_AT_LEAST(3, 5)
      recordValue("type", d->getCallResultType().getAsString(printPolicy));
#else
      recordValue("type", d->getResultType().getAsString(printPolicy));
#endif
      std::string args("(");
      for (FunctionDecl::param_iterator it = d->param_begin();
          it != d->param_end(); it++) {
        args += ", ";
        args += (*it)->getType().getAsString(printPolicy);
      }
      if (d->getNumParams() > 0)
        args.erase(1, 2);
      args += ")";
      recordValue("args", args);
      SourceLocation beginLoc = d->getNameInfo().getBeginLoc();
      recordValue("loc", locationToString(beginLoc));
      recordLocEndForName(functionName, beginLoc, d->getNameInfo().getEndLoc());
      printScope(d);
      *out << std::endl;

      // Print out overrides
      if (CXXMethodDecl::classof(d)) {  // It's a method.
        CXXMethodDecl *methodDecl = dyn_cast<CXXMethodDecl>(d);

        // What do we override?
        for (CXXMethodDecl::method_iterator iter =
               methodDecl->begin_overridden_methods(),
               end = methodDecl->end_overridden_methods();
             iter != end; ++iter) {
          const FunctionDecl *overriddenDecl = *iter;
          if (!interestingLocation(overriddenDecl->getLocation()))
            continue;
          beginRecord("func_override", functionLocation);
          recordValue("name", functionName);
          recordValue("qualname", functionQualName);
          recordValue("overriddenname", overriddenDecl->getNameAsString());
          recordValue("overriddenqualname", getQualifiedName(*overriddenDecl));
          *out << std::endl;
        }
      }
    }

    const FunctionDecl *def = nullptr;
    d->isDefined(def);
    declDef("function", d, def,
            d->getNameInfo().getBeginLoc(), d->getNameInfo().getEndLoc());

    return true;
  }

  bool VisitCXXConstructorDecl(CXXConstructorDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;

    for (CXXConstructorDecl::init_const_iterator it = d->init_begin(),
           e = d->init_end();
         it != e; ++it) {
      const CXXCtorInitializer *ci = *it;
      if (!ci->getMember() || !ci->isWritten())
        continue;
      printReference("variable", ci->getMember(),
                     ci->getMemberLocation(), ci->getMemberLocation());
    }

    return true;
  }

  bool treatThisValueDeclAsADefinition(const ValueDecl *d) {
    const VarDecl *vd = dyn_cast<VarDecl>(d);
    if (!vd) {
      // Things that are not VarDecls (FieldDecl, EnumConstantDecl) are always
      // treated as definitions.
      return true;
    }
    if (!vd->isThisDeclarationADefinition())
      return false;
    if (!isa<ParmVarDecl>(d))
      return true;
    // This var is part of a parameter list.  Only treat it as
    // a definition if a function is also being defined.
    const FunctionDecl *fd = dyn_cast<FunctionDecl>(d->getDeclContext());
    return fd && fd->isThisDeclarationADefinition();
  }

  std::string getValueForValueDecl(ValueDecl *d) {
    if (const VarDecl *vd = dyn_cast<VarDecl>(d)) {
      const Expr *init = vd->getAnyInitializer(vd);
      if (!isa<ParmVarDecl>(vd) &&
          init && !init->getType().isNull() && !init->isValueDependent() &&
          vd->getType().isConstQualified()) {
        if (const APValue *apv = vd->evaluateValue()) {
          std::string ret = apv->getAsString(vd->getASTContext(), vd->getType());
          // Workaround for constant strings being shown as &"foo" or &"foo"[0]
          if (str_starts_with(ret, "&\"")) {
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
    SourceLocation location = escapeMacros(d->getLocation());
    if (!interestingLocation(location)) {
      return;
    }
    if (treatThisValueDeclAsADefinition(d)) {
      beginRecord("variable", location);
      recordValue("name", d->getNameAsString());
      recordValue("qualname", getQualifiedName(*d));
      recordValue("loc", locationToString(location));
      recordValue("locend", locationToString(afterToken(location)));
      recordValue("type", d->getType().getAsString(printPolicy));
      const std::string &value = getValueForValueDecl(d);
      if (!value.empty())
        recordValue("value", value);
      printScope(d);
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
        VarDecl *lastTentative = nullptr;
        for (VarDecl::redecl_iterator i = first->redecls_begin(),
               e = first->redecls_end();
             i != e; ++i) {
          VarDecl::DefinitionKind kind = i->isThisDeclarationADefinition();
          if (kind == VarDecl::TentativeDefinition) {
            lastTentative = *i;
          }
        }
        def = lastTentative;
      }
      // TODO: See if there's a vd->getNameInfo(), as in other calls we make to
      // declDef.
      declDef("variable", vd, def,
              vd->getLocation(), afterToken(vd->getLocation()));
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
    if (TagType::classof(real)) {
      DiagnosticsEngine &D = CI.getDiagnostics();
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
    recordValue("locend", locationToString(afterToken(d->getLocation())));
    printScope(d);
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

    // TODO: d->getNameInfo()?
    recordValue("locend", locationToString(afterToken(d->getLocation())));
    printScope(d);
    *out << std::endl;
    return true;
  }

  // Like "namespace foo;".
  bool VisitNamespaceDecl(NamespaceDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;
    beginRecord("namespace", d->getLocation());
    recordValue("name", d->getNameAsString());
    recordValue("qualname", getQualifiedName(*d));
    recordValue("loc", locationToString(d->getLocation()));
    recordValue("locend", locationToString(afterToken(d->getLocation())));
    *out << std::endl;
    return true;
  }

  // Like "namespace bar = foo;"
  bool VisitNamespaceAliasDecl(NamespaceAliasDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;

    beginRecord("namespace_alias", d->getAliasLoc());
    recordValue("name", d->getNameAsString());
    recordValue("qualname", getQualifiedName(*d));
    recordValue("loc", locationToString(d->getAliasLoc()));
    recordValue("locend", locationToString(afterToken(d->getAliasLoc())));
    *out << std::endl;

    if (d->getQualifierLoc())
      visitNestedNameSpecifierLoc(d->getQualifierLoc());
    printReference("namespace", d->getAliasedNamespace(),
                   d->getTargetNameLoc(), d->getTargetNameLoc());
    return true;
  }

  // Like "using namespace std;"
  bool VisitUsingDirectiveDecl(UsingDirectiveDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;
    if (d->getQualifierLoc())
      visitNestedNameSpecifierLoc(d->getQualifierLoc());
    printReference("namespace", d->getNominatedNamespace(),
                   d->getIdentLocation(), d->getIdentLocation());
    return true;
  }

  // Like "using std::string;"
  bool VisitUsingDecl(UsingDecl *d) {
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
  void printReference(const char *kind, NamedDecl *d,
                      SourceLocation refLoc, SourceLocation end) {
    if (!interestingLocation(refLoc))
      return;
    SourceLocation nonMacroRefLoc = escapeMacros(refLoc);
    std::string name = d->getNameAsString();
    beginRecord("ref", nonMacroRefLoc);
    if (interestingLocation(d->getLocation()))
      recordValue("defloc", locationToString(d->getLocation()));
    recordValue("loc", locationToString(nonMacroRefLoc));
    recordLocEndForName(name, nonMacroRefLoc, escapeMacros(end));
    if (kind)
      recordValue("kind", kind);
    recordValue("name", name);
    recordValue("qualname", getQualifiedName(*d));
    *out << std::endl;
  }

  const char *kindForDecl(const Decl *d) {
    if (isa<FunctionDecl>(d))
      return "function";
    if (isa<EnumConstantDecl>(d) || isa<VarDecl>(d) || isa<FieldDecl>(d))
      return "variable";
    return nullptr;  // Unhandled for now
  }

  bool VisitMemberExpr(MemberExpr *e) {
    ValueDecl *vd = e->getMemberDecl();
    if (FieldDecl *fd = dyn_cast<FieldDecl>(vd)) {
      /* Ignore references to a anonymous structs and unions.
       * We can't do anything useful with them and they overlap with the
       * reference to the member inside the struct/union causing us to
       * effectively lose that other reference. */
      if (fd->isAnonymousStructOrUnion())
        return true;
    }
    printReference(kindForDecl(vd),
                   vd,
                   e->getExprLoc(),
                   e->getMemberNameInfo().getEndLoc());
    return true;
  }

  bool VisitDeclRefExpr(DeclRefExpr *e) {
    if (e->hasQualifier())
      visitNestedNameSpecifierLoc(e->getQualifierLoc());
    SourceLocation start = e->getNameInfo().getBeginLoc();
    SourceLocation end = e->getNameInfo().getEndLoc();
    if (end.isInvalid())
        end = start;
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
    if (!callee || !NamedDecl::classof(callee))
      return true;

    const NamedDecl *namedCallee = dyn_cast<NamedDecl>(callee);

    // Fun facts about call exprs:
    // 1. callee isn't necessarily a function. Think function pointers.
    // 2. We might not be in a function. Think global function decls
    // 3. Virtual functions need not be called virtually!
    beginRecord("call", e->getLocStart());
    recordValue("callloc", locationToString(e->getLocStart()));
    recordValue("calllocend", locationToString(e->getLocEnd()));
    if (interestingLocation(callee->getLocation()))
      recordValue("calleeloc", locationToString(callee->getLocation()));
    recordValue("name", namedCallee->getNameAsString());
    recordValue("qualname", getQualifiedName(*namedCallee));
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
    if (!callee || !NamedDecl::classof(callee))
      return true;

    // Fun facts about call exprs:
    // 1. callee isn't necessarily a function. Think function pointers.
    // 2. We might not be in a function. Think global function decls
    // 3. Virtual functions need not be called virtually!
    beginRecord("call", e->getLocStart());
    recordValue("callloc", locationToString(e->getLocStart()));
    recordValue("calllocend", locationToString(e->getLocEnd()));
    if (interestingLocation(callee->getLocation()))
      recordValue("calleeloc", locationToString(callee->getLocation()));
    recordValue("name", callee->getNameAsString());
    recordValue("qualname", getQualifiedName(*callee));

    // There are no virtual constructors in C++:
    recordValue("calltype", "static");

    *out << std::endl;
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
    // TODO: It seems like a lot of the (presumably working) old stuff used
    // getBeginLoc and getEndLoc. Try switching to those where available if
    // things don't work.
    return true;
  }

  SourceLocation removeTrailingColonColon(SourceLocation begin,
                                          SourceLocation end) {
    if (!end.isValid())
      return end;

    SmallVector<char, 32> buffer;
    if (Lexer::getSpelling(end, buffer, sm, features) != "::") {
      // Doesn't descend any deeper into a "spelling" or "expansion" location
      // than the location already is.
      return end;
    }

    SourceLocation prev;
    for (SourceLocation loc = begin;
         loc.isValid() && loc != end && loc != prev;
         loc = afterToken(loc)) {
      prev = loc;
    }

    return prev.isValid() ? prev : end;
  }

  void visitNestedNameSpecifierLoc(NestedNameSpecifierLoc l) {
    if (!interestingLocation(l.getBeginLoc()))
      return;

    if (l.getPrefix())
      visitNestedNameSpecifierLoc(l.getPrefix());

    SourceLocation begin = l.getLocalBeginLoc(),
                   end = l.getLocalEndLoc();
    // We don't want the "::" to be part of the link.
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
      if (sm.isMacroArgExpansion(loc)) {
        // TODO: Why do we want to attach the warning to the macro definition
        // site rather than its use?
        loc = sm.getImmediateSpellingLoc(loc);
      } else {
#if CLANG_AT_LEAST(7, 0)
        loc = sm.getImmediateExpansionRange(loc).getBegin();
#else
        loc = sm.getImmediateExpansionRange(loc).first;
#endif
      }
    }
    return loc;
  }

  void HandleDiagnostic(DiagnosticsEngine::Level level,
      const Diagnostic &info) override {
    DiagnosticConsumer::HandleDiagnostic(level, info);
    inner->HandleDiagnostic(level, info);
    if (level != DiagnosticsEngine::Warning ||
        !interestingLocation(info.getLocation()))
      return;

    llvm::SmallString<100> message;
    info.FormatDiagnostic(message);

    beginRecord("warning", info.getLocation());
    recordValue("msg", message.c_str());
    StringRef opt = DiagnosticIDs::getWarningOptionForDiag(info.getID());
    if (!opt.empty())
      recordValue("opt", ("-W" + opt).str());
    if (info.getNumRanges() > 0) {
      const CharSourceRange &range = info.getRange(0);
      SourceLocation warningBeginning = getWarningExtentLocation(range.getBegin());
      SourceLocation warningEnd = getWarningExtentLocation(afterToken(range.getEnd()));
      recordValue("loc", locationToString(warningBeginning));
      recordValue("locend", locationToString(warningEnd));
    } else {
      SourceLocation loc = getWarningExtentLocation(info.getLocation());
      recordValue("loc", locationToString(loc));
      // This isn't great, but it's basically what it did before, via
      // printExtent.
      recordValue("locend", locationToString(afterToken(loc)));
    }
    *out << std::endl;
  }

  // Macros!
  void MacroDefined(const Token &MacroNameTok, const MacroInfo *MI) {
    if (MI->isBuiltinMacro() || !interestingLocation(MI->getDefinitionLoc()))
      return;

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
      for (argsEnd = nameLen + 1; argsEnd < length; argsEnd++) {
        if (contents[argsEnd] == ')') {
          argsEnd++;
          break;
        }
      }
      defnStart = argsEnd;
    } else {
      defnStart = nameLen;
    }
    bool hasArgs = (argsEnd - argsStart > 2);  // An empty '()' doesn't count.
    if (!hasArgs) {
      // Skip leading whitespace in the definition up to and including any first
      // line continuation.
      for (; defnStart < length; defnStart++) {
        switch (contents[defnStart]) {
          case ' ': case '\t': case '\v': case '\r': case '\n': case '\f':
            continue;
          case '\\':
            if (defnStart + 2 < length && contents[defnStart + 1] == '\n') {
              defnStart += 2;
            }
            break;
        }
        break;
      }
    }
    beginRecord("macro", nameStart);
    recordValue("loc", locationToString(nameStart));
    recordValue("locend", locationToString(afterToken(nameStart)));
    recordValue("name", std::string(contents, nameLen));
    if (defnStart < length) {
      std::string text;
      if (hasArgs)  // Give the argument list.
        text = std::string(contents + argsStart, argsEnd - argsStart);
      text += std::string(contents + defnStart, length - defnStart);
      // FIXME: handle non-ASCII characters better
      for (size_t i = 0; i < text.size(); ++i) {
        if ((text[i] < ' ' || text[i] >= 0x7F) &&
            text[i] != '\t' && text[i] != '\n')
          text[i] = '?';
      }
      macromap.insert(make_pair(nameStart, text));
    }
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
    recordValue("defloc", locationToString(macroLoc));
    recordValue("loc", locationToString(refLoc));
    recordValue("locend", locationToString(afterToken(refLoc)));
    recordValue("kind", "macro");
    std::map<SourceLocation, std::string>::const_iterator it =
      macromap.find(macroLoc);
    if (it != macromap.end()) {
      recordValue("text", it->second);
    }
    *out << std::endl;
  }

  void MacroExpands(const Token &tok, const MacroInfo *MI, SourceRange Range) {
    printMacroReference(tok, MI);
  }
  void MacroUndefined(const Token &tok, const MacroInfo *MI) {
    printMacroReference(tok, MI);
  }
  void Defined(const Token &tok, const MacroInfo *MI) {
    printMacroReference(tok, MI);
  }
  void Ifdef(SourceLocation loc, const Token &tok, const MacroInfo *MI) {
    printMacroReference(tok, MI);
  }
  void Ifndef(SourceLocation loc, const Token &tok, const MacroInfo *MI) {
    printMacroReference(tok, MI);
  }

  void InclusionDirective(
      SourceLocation hashLoc,
      const Token &includeTok,
      StringRef fileName,
      bool isAngled,
      CharSourceRange filenameRange,
      const FileEntry *file,
      StringRef searchPath,
      StringRef relativePath,
      const Module *imported) {
    PresumedLoc presumedHashLoc = sm.getPresumedLoc(hashLoc);
    if (!interestingLocation(hashLoc) ||
        filenameRange.isInvalid() ||
        presumedHashLoc.isInvalid())
      return;

    // Don't record inclusions of files that are outside the source tree,
    // like stdlibs. file is NULL if an #include can't be resolved, like if
    // you include a nonexistent file.
    if (!file)
      return;

    const FileInfoPtr &target = getFileInfo(file->getName());
    if (!target->interesting)
      return;

    // TODO: Come up with some kind of reasonable extent for macro-based
    // includes, like #include FOO_MACRO.
    const SourceLocation targetBegin = filenameRange.getBegin();
    const SourceLocation targetEnd = filenameRange.getEnd();
    if (targetBegin.isMacroID() || targetEnd.isMacroID())
      return;

    const FileInfoPtr &source = getFileInfo(presumedHashLoc.getFilename());
    // TODO: Support generated files once we run the trigram indexer over
    // them. For now, we skip them.
    if (!(source->realname.compare(0, GENERATED.size(), GENERATED)) ||
        !(target->realname.compare(0, GENERATED.size(), GENERATED)))
      return;

    beginRecord("include", hashLoc);
    recordValue("source_path", source->realname);
    recordValue("target_path", target->realname);
    recordValue("loc", locationToString(targetBegin));
    recordValue("locend", locationToString(targetEnd));
    *out << std::endl;
  }

};

#if CLANG_AT_LEAST(3, 3)
void PreprocThunk::MacroDefined(const Token &tok, const MacroDirective *md) {
  real->MacroDefined(tok, md->getMacroInfo());
}
  #if CLANG_AT_LEAST(3, 7)
  void PreprocThunk::MacroExpands(const Token &tok, const MacroDefinition &md,
                                  SourceRange range, const MacroArgs *ma) {
    real->MacroExpands(tok, md.getMacroInfo(), range);
  }
    #if CLANG_AT_LEAST(5, 0)
  void PreprocThunk::MacroUndefined(const Token &tok, const MacroDefinition &md,
                                    const MacroDirective */*Undef*/) {
    real->MacroUndefined(tok, md.getMacroInfo());
  }
    #else
  void PreprocThunk::MacroUndefined(const Token &tok, const MacroDefinition &md) {
    real->MacroUndefined(tok, md.getMacroInfo());
  }
    #endif
  void PreprocThunk::Ifdef(SourceLocation loc, const Token &tok,
                           const MacroDefinition &md) {
    real->Ifdef(loc, tok, md.getMacroInfo());
  }
  void PreprocThunk::Ifndef(SourceLocation loc, const Token &tok,
                            const MacroDefinition &md) {
    real->Ifndef(loc, tok, md.getMacroInfo());
  }
  #else
  void PreprocThunk::MacroExpands(const Token &tok, const MacroDirective *md,
                                  SourceRange range, const MacroArgs *ma) {
    real->MacroExpands(tok, md->getMacroInfo(), range);
  }
  void PreprocThunk::MacroUndefined(const Token &tok, const MacroDirective *md) {
    real->MacroUndefined(tok, md->getMacroInfo());
  }
  void PreprocThunk::Ifdef(SourceLocation loc, const Token &tok,
                           const MacroDirective *md) {
    real->Ifdef(loc, tok, md->getMacroInfo());
  }
  void PreprocThunk::Ifndef(SourceLocation loc, const Token &tok,
                            const MacroDirective *md) {
    real->Ifndef(loc, tok, md->getMacroInfo());
  }
  #endif
  #if CLANG_AT_LEAST(3, 7)
  void PreprocThunk::Defined(const Token &tok, const MacroDefinition &md,
                             SourceRange range) {
    real->Defined(tok, md.getMacroInfo());
  }
  #elif CLANG_AT_LEAST(3, 4)
  void PreprocThunk::Defined(const Token &tok, const MacroDirective *md,
                             SourceRange) {
    real->Defined(tok, md->getMacroInfo());
  }
  #else
  void PreprocThunk::Defined(const Token &tok, const MacroDirective *md) {
    real->Defined(tok, md->getMacroInfo());
  }
  #endif
#else  // clang < 3.3
void PreprocThunk::MacroDefined(const Token &tok, const MacroInfo *MI) {
  real->MacroDefined(tok, MI);
}
void PreprocThunk::MacroExpands(const Token &tok, const MacroInfo *MI,
                                SourceRange Range) {
  real->MacroExpands(tok, MI, Range);
}
void PreprocThunk::MacroUndefined(const Token &tok, const MacroInfo *MI) {
  real->MacroUndefined(tok, MI);
}
void PreprocThunk::Defined(const Token &tok) {
  real->Defined(tok, nullptr);
}
void PreprocThunk::Ifdef(SourceLocation loc, const Token &tok) {
  real->Ifdef(loc, tok, nullptr);
}
void PreprocThunk::Ifndef(SourceLocation loc, const Token &tok) {
  real->Ifndef(loc, tok, nullptr);
}
#endif
#if CLANG_AT_LEAST(7, 0)
void PreprocThunk::InclusionDirective(
    SourceLocation hashLoc,
    const Token &includeTok,
    StringRef fileName,
    bool isAngled,
    CharSourceRange filenameRange,
    const FileEntry *file,
    StringRef searchPath,
    StringRef relativePath,
    const Module *imported,
    SrcMgr::CharacteristicKind) {
  real->InclusionDirective(hashLoc, includeTok, fileName, isAngled, filenameRange,
                           file, searchPath, relativePath, imported);
}
#else
void PreprocThunk::InclusionDirective(
    SourceLocation hashLoc,
    const Token &includeTok,
    StringRef fileName,
    bool isAngled,
    CharSourceRange filenameRange,
    const FileEntry *file,
    StringRef searchPath,
    StringRef relativePath,
    const Module *imported) {
  real->InclusionDirective(hashLoc, includeTok, fileName, isAngled, filenameRange,
                           file, searchPath, relativePath, imported);
}
#endif

// Our plugin entry point.
class DXRIndexAction : public PluginASTAction {
protected:
#if CLANG_AT_LEAST(3, 6)
  std::unique_ptr<ASTConsumer> CreateASTConsumer(CompilerInstance &CI,
                                                 llvm::StringRef f) override {
    return std::unique_ptr<ASTConsumer>(new IndexConsumer(CI));
#else
  ASTConsumer *CreateASTConsumer(CompilerInstance &CI,
                                 llvm::StringRef f) override {
    return new IndexConsumer(CI);
#endif
  }

  bool ParseArgs(const CompilerInstance &CI,
                 const std::vector<std::string>& args) override {
    if (args.empty()) {
      DiagnosticsEngine &D = CI.getDiagnostics();
      unsigned DiagID = D.getCustomDiagID(DiagnosticsEngine::Error,
        "Need an argument for the source directory");
      D.Report(DiagID);
      return false;
    }
    // Load our directories.

    // The source directory. Follow the GCC/Clang convention of picking the
    // the value of the argument that has been specificed last in the command
    // line.
    char *abs_src = realpath(args.back().c_str(), nullptr);
    if (!abs_src) {
      DiagnosticsEngine &D = CI.getDiagnostics();
      unsigned DiagID = D.getCustomDiagID(DiagnosticsEngine::Error,
        "Source directory '%0' does not exist");
      D.Report(DiagID) << args[0];
      return false;
    }
    FileInfo::srcdir = std::string(abs_src) + "/";

    // The build output directory.
    const char *env = getenv("DXR_CXX_CLANG_OBJECT_FOLDER");
    std::string output = env ? env : abs_src;
    free(abs_src);

    char *abs_output = realpath(output.c_str(), nullptr);
    if (!abs_output) {
      DiagnosticsEngine &D = CI.getDiagnostics();
      unsigned DiagID = D.getCustomDiagID(DiagnosticsEngine::Error,
        "Output directory '%0' does not exist");
      D.Report(DiagID) << output;
      return false;
    }
    output = abs_output;
    output += "/";
    FileInfo::output = output;
    free(abs_output);

    // The temp directory for this plugin's output.
    const char *tmp = getenv("DXR_CXX_CLANG_TEMP_FOLDER");
    std::string tmpdir = tmp ? tmp : output;
    char *abs_tmpdir = realpath(tmpdir.c_str(), nullptr);
    if (!abs_tmpdir) {
      DiagnosticsEngine &D = CI.getDiagnostics();
      unsigned DiagID = D.getCustomDiagID(DiagnosticsEngine::Error,
        "Temporary directory '%0' does not exist");
      D.Report(DiagID) << tmpdir;
      return false;
    }
    tmpdir = abs_tmpdir;
    tmpdir += "/";
    IndexConsumer::setTmpDir(tmpdir);
    free(abs_tmpdir);

    return true;
  }
};

// define static members
std::string FileInfo::srcdir;
std::string FileInfo::output;
std::string IndexConsumer::tmpdir;
}

static FrontendPluginRegistry::Add<DXRIndexAction>
X("dxr-index", "create the dxr index database");
