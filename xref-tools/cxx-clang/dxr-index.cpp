//===- PrintFunctionNames.cpp ---------------------------------------------===//
//
//                     The LLVM Compiler Infrastructure
//
// This file is distributed under the University of Illinois Open Source
// License. See LICENSE.TXT for details.
//
//===----------------------------------------------------------------------===//
//
// Example clang plugin which simply prints the names of all the top-level decls
// in the input file.
//
//===----------------------------------------------------------------------===//

#include "clang/AST/AST.h"
#include "clang/AST/ASTConsumer.h"
#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Frontend/FrontendPluginRegistry.h"
#include "llvm/Support/raw_ostream.h"

#include <fstream>
#include <stdio.h>
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
public:
  IndexConsumer(CompilerInstance &ci, const char *file) :
    sm(ci.getSourceManager()), out(file) {}
  
  // Helpers for processing declarations
  // Should we ignore this location?
  bool interestingLocation(SourceLocation loc) {
    std::string filename = sm.getBufferName(loc, NULL);
    // Invalid locations and built-ins: not interesting at all
    if (filename[0] == '<')
      return false;
    return true;
  }

  std::string locationToString(SourceLocation loc) {
    std::string buffer = sm.getBufferName(loc, NULL);
    buffer += ":";
    buffer += sm.getSpellingLineNumber(loc);
    return buffer;
  }

  void printScope(Decl *d) {
    Decl *ctxt = Decl::castFromDeclContext(d->getNonClosureContext());
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
    out << "type,tname,\"" << d->getQualifiedNameAsString() << "\",tloc,\"" <<
      locationToString(d->getLocation()) << "\",tkind," << d->getKindName() <<
      std::endl;

    declDef(d, d->getDefinition());
    // XXX: inheritance
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
    out << "typedef,tname,\"" << d->getQualifiedNameAsString() <<
      "\",tloc,\"" << locationToString(d->getLocation()) << "\"";
    // XXX: printout the referent
    out << std::endl;
    return true;
  }

  bool VisitDecl(Decl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;
    if (!TagDecl::classof(d) && !NamespaceDecl::classof(d) &&
        !FunctionDecl::classof(d) && !FieldDecl::classof(d) &&
        !VarDecl::classof(d) && !TypedefNameDecl::classof(d) &&
        !EnumConstantDecl::classof(d))
      printf("Unprocessed kind %s\n", d->getDeclKindName());
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
