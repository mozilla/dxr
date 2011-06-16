#include "clang/AST/AST.h"
#include "clang/AST/ASTConsumer.h"
#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Frontend/FrontendPluginRegistry.h"
#include "clang/Lex/Lexer.h"
#include "llvm/Support/raw_ostream.h"

#include <fstream>
#include <stdio.h>
#include <stdlib.h>
using namespace clang;

namespace {

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

class IndexConsumer : public ASTConsumer,
    public RecursiveASTVisitor<IndexConsumer> {
private:
  SourceManager &sm;
  std::ofstream out;
  LangOptions &features;
public:
  IndexConsumer(CompilerInstance &ci, const char *file) :
    sm(ci.getSourceManager()), out(file), features(ci.getLangOpts()) {}
  
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
    if (filename[0] != '/') // Relative path, keep it
      return true;
    return filename.find("/src/OpenSkyscraper/") == 0;
  }

  std::string locationToString(SourceLocation loc) {
    PresumedLoc fixed = sm.getPresumedLoc(loc);
    std::string buffer = realpath(fixed.getFilename(), NULL);
    buffer += ":";
    buffer += fixed.getLine();
    buffer += ":";
    buffer += fixed.getColumn();
    return buffer;
  }

  void printScope(Decl *d) {
    Decl *ctxt = Decl::castFromDeclContext(d->getNonClosureContext());
    // Ignore namespace scopes, since it doesn't really help for source code
    // organization
    while (NamespaceDecl::classof(ctxt))
      ctxt = Decl::castFromDeclContext(ctxt->getNonClosureContext());
    if (NamedDecl::classof(ctxt)) {
      NamedDecl *scope = static_cast<NamedDecl*>(ctxt);
      out << ",scopename,\"" << scope->getQualifiedNameAsString() <<
        "\",scopeloc,\"" << locationToString(scope->getLocation()) << "\"";
    }
  }

  void declDef(const NamedDecl *decl, const NamedDecl *def) {
    if (!def)
      return;

    out << "decldef,name,\"" << decl->getQualifiedNameAsString() <<
      "\",declloc,\"" << locationToString(decl->getLocation()) <<
      "\",defloc,\"" << locationToString(def->getLocation()) << "\"" <<
      std::endl;
  }

  // All we need is to follow the final declaration.
  virtual void HandleTranslationUnit(ASTContext &ctx) {
    TraverseDecl(ctx.getTranslationUnitDecl());
  }

  // Tag declarations: class, struct, union, enum
  bool VisitTagDecl(TagDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;
    // Information we need for types: kind, fqname, simple name, location
    out << "type,tname,\"" << d->getNameAsString() << "\",tqualname,\"" <<
      d->getQualifiedNameAsString() << "\",tloc,\"" <<
      locationToString(d->getLocation()) << "\",tkind," << d->getKindName();
    printScope(d);
    out << std::endl;

    declDef(d, d->getDefinition());
    return true;
  }

  bool VisitCXXRecordDecl(CXXRecordDecl *d) {
    if (!interestingLocation(d->getLocation()) || !d->isDefinition())
      return true;

    // TagDecl already did decldef and type outputting; we just need impl
    for (CXXRecordDecl::base_class_iterator iter = d->bases_begin();
        iter != d->bases_end(); ++iter) {
      CXXRecordDecl *base = (*iter).getType()->getAsCXXRecordDecl();
      out << "impl,tcname,\"" << d->getQualifiedNameAsString() <<
        "\",tcloc,\"" << locationToString(d->getLocation()) << "\",tbname,\"" <<
        base->getQualifiedNameAsString() << "\",tbloc,\"" <<
        locationToString(base->getLocation()) << "\",access,\"";
      switch ((*iter).getAccessSpecifierAsWritten()) {
      case AS_public: out << "public"; break;
      case AS_protected: out << "protected"; break;
      case AS_private: out << "private"; break;
      case AS_none: break; // It's implied, but we can ignore that
      }
      if ((*iter).isVirtual())
        out << " virtual";
      out << "\"" << std::endl;
    }
    return true;
  }

  bool VisitFunctionDecl(FunctionDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;
    out << "function,fname,\"" << d->getNameAsString() << "\",flongname,\"" <<
      d->getQualifiedNameAsString() << "\",floc,\"" <<
      locationToString(d->getLocation()) << "\"";
    printScope(d);
    out << std::endl;
    const FunctionDecl *def;
    if (d->isDefined(def))
      declDef(d, def);
    return true;
  }

  void visitVariableDecl(ValueDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return;
    out << "variable,vname,\"" << d->getQualifiedNameAsString() <<
      "\",vloc,\"" << locationToString(d->getLocation()) << "\"";
    printScope(d);
    out << std::endl;
  }

  bool VisitEnumConstandDecl(EnumConstantDecl *d) { visitVariableDecl(d); return true; }
  bool VisitFieldDecl(FieldDecl *d) { visitVariableDecl(d); return true; }
  bool VisitVarDecl(VarDecl *d) { visitVariableDecl(d); return true; }

  bool VisitTypedefNameDecl(TypedefNameDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;
    out << "typedef,tname,\"" << d->getNameAsString() << "\",tqualname,\"" <<
      d->getQualifiedNameAsString() << "\",tloc,\"" <<
      locationToString(d->getLocation()) << "\"";
    // XXX: printout the referent
    printScope(d);
    out << std::endl;
    return true;
  }

  bool VisitDecl(Decl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;
    if (!TagDecl::classof(d) && !NamespaceDecl::classof(d) &&
        !FunctionDecl::classof(d) && !FieldDecl::classof(d) &&
        !VarDecl::classof(d) && !TypedefNameDecl::classof(d) &&
        !EnumConstantDecl::classof(d) && !AccessSpecDecl::classof(d))
      printf("Unprocessed kind %s\n", d->getDeclKindName());
    return true;
  }

  // Expressions!
  void printReference(NamedDecl *d, SourceLocation refLoc, SourceLocation end) {
    if (!interestingLocation(d->getLocation()) || !interestingLocation(refLoc))
      return;
    std::string filename = sm.getBufferName(refLoc, NULL);
    if (filename.empty())
      // Basically, this means we're in a macro expansion and we have serious
      // preprocessing stuff going on (i.e., ## and possibly #). Just bail for
      // now.
      return;
    out << "ref,varname,\"" << d->getQualifiedNameAsString() <<
      "\",varloc,\"" << locationToString(d->getLocation()) << "\",refloc,\"" <<
      locationToString(refLoc) << "\",extent," << sm.getFileOffset(refLoc) <<
      ":" << sm.getFileOffset(Lexer::getLocForEndOfToken(end, 0, sm, features))
      << std::endl;
  }
  bool VisitMemberExpr(MemberExpr *e) {
    printReference(e->getMemberDecl(), e->getExprLoc(), e->getSourceRange().getEnd());
    return true;
  }
  bool VisitDeclRefExpr(DeclRefExpr *e) {
    printReference(e->getDecl(), e->hasQualifier() ?
      e->getQualifierLoc().getBeginLoc() : e->getLocation(), e->getNameInfo().getEndLoc());
    return true;
  }

  // Type locators
  bool VisitTagTypeLoc(TagTypeLoc l) {
    if (!interestingLocation(l.getBeginLoc()))
      return true;

    printReference(l.getDecl(), l.getBeginLoc(), l.getEndLoc());
    return true;
  }
};

class DXRIndexAction : public PluginASTAction {
protected:
  ASTConsumer *CreateASTConsumer(CompilerInstance &CI, llvm::StringRef f) {
    return new IndexConsumer(CI, (f.str() + ".csv").c_str());
  }

  bool ParseArgs(const CompilerInstance &CI,
                 const std::vector<std::string>& args) {
    for (unsigned i = 0, e = args.size(); i != e; ++i) {
      llvm::errs() << "PrintFunctionNames arg = " << args[i] << "\n";

      // Example error handling.
      if (args[i] == "-an-error") {
        Diagnostic &D = CI.getDiagnostics();
        unsigned DiagID = D.getCustomDiagID(
          Diagnostic::Error, "invalid argument '" + args[i] + "'");
        D.Report(DiagID);
        return false;
      }
    }
    if (args.size() && args[0] == "help")
      PrintHelp(llvm::errs());

    return true;
  }
  void PrintHelp(llvm::raw_ostream& ros) {
    ros << "Help for PrintFunctionNames plugin goes here\n";
  }

};

}

static FrontendPluginRegistry::Add<DXRIndexAction>
X("dxr-index", "create the dxr index database");
