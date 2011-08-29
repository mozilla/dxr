#include "clang/AST/AST.h"
#include "clang/AST/ASTConsumer.h"
#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Frontend/FrontendPluginRegistry.h"
#include "clang/Lex/Lexer.h"
#include "clang/Lex/Preprocessor.h"
#include "clang/Lex/PPCallbacks.h"
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
      realname.replace(0, output.length(), "--GENERATED--/");
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
  virtual void MacroDefined(const Token &MacroNameTok, const MacroInfo *MI);
  virtual void MacroExpands(const Token &MacroNameTok, const MacroInfo *MI, SourceRange Range);
};

class IndexConsumer : public ASTConsumer,
    public RecursiveASTVisitor<IndexConsumer>,
    public PPCallbacks,
    public DiagnosticConsumer {
private:
  CompilerInstance &ci;
  SourceManager &sm;
  std::ostream *out;
  std::map<std::string, FileInfo *> relmap;
  LangOptions &features;
  DiagnosticConsumer *inner;

  FileInfo *getFileInfo(std::string &filename) {
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

  void printExtent(SourceLocation begin, SourceLocation end) {
    if (begin.isMacroID() || end.isMacroID())
      return;
    *out << ",extent," << sm.getDecomposedSpellingLoc(begin).second << ":" <<
      sm.getDecomposedSpellingLoc(
        Lexer::getLocForEndOfToken(end, 0, sm, features)).second;
  }

  void printScope(Decl *d) {
    Decl *ctxt = Decl::castFromDeclContext(d->getNonClosureContext());
    // Ignore namespace scopes, since it doesn't really help for source code
    // organization
    while (NamespaceDecl::classof(ctxt))
      ctxt = Decl::castFromDeclContext(ctxt->getNonClosureContext());
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
      recordValue("scopename", namesource->getQualifiedNameAsString());
      recordValue("scopeloc", locationToString(scope->getLocation()));
    }
  }

  void declDef(const NamedDecl *decl, const NamedDecl *def) {
    if (!def)
      return;

    beginRecord("decldef", decl->getLocation());
    recordValue("name", decl->getQualifiedNameAsString());
    recordValue("declloc", locationToString(decl->getLocation()));
    recordValue("defloc", locationToString(def->getLocation()));
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
      std::string filename = output;
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
    // Information we need for types: kind, fqname, simple name, location
    beginRecord("type", d->getLocation());
    // We get the name from the typedef if it's an anonymous declaration...
    NamedDecl *nd = d->getTypedefNameForAnonDecl();
    if (!nd)
      nd = d;
    recordValue("tname", nd->getNameAsString());
    recordValue("tqualname", nd->getQualifiedNameAsString());
    recordValue("tloc", locationToString(d->getLocation()));
    recordValue("tkind", d->getKindName());
    printScope(d);
    // Linkify the name, not the `enum'
    printExtent(nd->getLocation(), nd->getLocation());
    *out << std::endl;

    declDef(d, d->getDefinition());
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
      recordValue("tcname", d->getQualifiedNameAsString());
      recordValue("tcloc", locationToString(d->getLocation()));
      recordValue("tbname", base->getQualifiedNameAsString());
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
    beginRecord("function", d->getLocation());
    recordValue("fname", d->getNameAsString());
    recordValue("fqualname", d->getQualifiedNameAsString());
    recordValue("ftype", d->getResultType().getAsString());
    std::string args("(");
    for (FunctionDecl::param_iterator it = d->param_begin();
        it != d->param_end(); it++) {
      args += ", ";
      args += (*it)->getType().getAsString();
    }
    if (d->getNumParams() > 0)
      args.erase(1, 2);
    args += ")";
    recordValue("fargs", args);
    recordValue("floc", locationToString(d->getLocation()));
    printScope(d);
    printExtent(d->getNameInfo().getBeginLoc(), d->getNameInfo().getEndLoc());
    // Print out overrides
    if (CXXMethodDecl::classof(d)) {
      CXXMethodDecl *cxxd = dyn_cast<CXXMethodDecl>(d);
      CXXMethodDecl::method_iterator iter = cxxd->begin_overridden_methods();
      if (iter) {
        recordValue("overridename", (*iter)->getQualifiedNameAsString());
        recordValue("overrideloc", locationToString((*iter)->getLocation()));
      }
    }
    *out << std::endl;
    const FunctionDecl *def;
    if (d->isDefined(def))
      declDef(d, def);
    return true;
  }

  void visitVariableDecl(ValueDecl *d) {
    if (!interestingLocation(d->getLocation()))
      return;
    beginRecord("variable", d->getLocation());
    recordValue("vname", d->getQualifiedNameAsString());
    recordValue("vloc", locationToString(d->getLocation()));
    recordValue("vtype", d->getType().getAsString());
    printScope(d);
    printExtent(d->getLocation(), d->getLocation());
    *out << std::endl;
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
      if (static_cast<const TagType*>(real)->getDecl()->
          getTypedefNameForAnonDecl() == d)
        return true;
    }
#endif
    beginRecord("typedef", d->getLocation());
    recordValue("tname", d->getNameAsString());
    recordValue("tqualname", d->getQualifiedNameAsString());
    recordValue("tloc", locationToString(d->getLocation()));
    recordValue("ttypedef", d->getUnderlyingType().getAsString());
    printScope(d);
    printExtent(d->getLocation(), d->getLocation());
    *out << std::endl;
    return true;
  }

  bool VisitDecl(Decl *d) {
    if (!interestingLocation(d->getLocation()))
      return true;
    if (!TagDecl::classof(d) && !NamespaceDecl::classof(d) &&
        !FunctionDecl::classof(d) && !FieldDecl::classof(d) &&
        !VarDecl::classof(d) && !TypedefNameDecl::classof(d) &&
        !EnumConstantDecl::classof(d) && !AccessSpecDecl::classof(d) &&
        !LinkageSpecDecl::classof(d))
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
    beginRecord("ref", refLoc);
    recordValue("varname", d->getQualifiedNameAsString());
    recordValue("varloc", locationToString(d->getLocation()));
    recordValue("refloc", locationToString(refLoc));
    printExtent(refLoc, end);
    *out << std::endl;
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
      recordValue("callername", m_currentFunction->getQualifiedNameAsString());
      recordValue("callerloc", locationToString(m_currentFunction->getLocation()));
    }
    recordValue("calleename", dyn_cast<NamedDecl>(callee)->getQualifiedNameAsString());
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

    printReference(l.getDecl(), l.getBeginLoc(), l.getEndLoc());
    return true;
  }

  // Warnings!
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
    recordValue("wloc", locationToString(info.getLocation()));
    recordValue("wmsg", message.c_str(), true);
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
    recordValue("macroloc", locationToString(nameStart));
    recordValue("macroname", std::string(contents, nameLen));
    if (argsStart > 0)
      recordValue("macroargs", std::string(contents + argsStart,
        argsEnd - argsStart), true);
    if (defnStart < length)
      recordValue("macrotext", std::string(contents + defnStart,
        length - defnStart), true);
    *out << std::endl;
  }
  virtual void MacroExpands(const Token &tok, const MacroInfo *MI, SourceRange Range) {
    if (MI->isBuiltinMacro()) return;
    if (!interestingLocation(tok.getLocation())) return;

    SourceLocation macroLoc = MI->getDefinitionLoc();
    SourceLocation refLoc = tok.getLocation();
    IdentifierInfo *name = tok.getIdentifierInfo();
    beginRecord("ref", refLoc);
    recordValue("varname", std::string(name->getNameStart(), name->getLength()));
    recordValue("varloc", locationToString(macroLoc));
    recordValue("refloc", locationToString(refLoc));
    printExtent(refLoc, refLoc);
    *out << std::endl;
  }
};

void PreprocThunk::MacroDefined(const Token &tok, const MacroInfo *MI) {
  real->MacroDefined(tok, MI);
}
  void PreprocThunk::MacroExpands(const Token &tok, const MacroInfo *MI, SourceRange Range) {
  real->MacroExpands(tok, MI, Range);
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
        "Source directory '" + args[0] + "' does not exist");
      D.Report(DiagID);
      return false;
    }
    srcdir = abs_src;
    const char *env = getenv("DXR_INDEX_OUTPUT");
    if (env)
      output = env;
    else
      output = srcdir;
    char *abs_output = realpath (output.c_str(), NULL);
    if (!abs_output) {
      DiagnosticsEngine &D = CI.getDiagnostics();
      unsigned DiagID = D.getCustomDiagID(DiagnosticsEngine::Error,
        "Output directory '" + output + "' does not exist");
      D.Report(DiagID);
      return false;
    }
    output = realpath(output.c_str(), NULL);
    output += "/";
    return true;
  }
  void PrintHelp(llvm::raw_ostream& ros) {
    ros << "Help for PrintFunctionNames plugin goes here\n";
  }

};

}

static FrontendPluginRegistry::Add<DXRIndexAction>
X("dxr-index", "create the dxr index database");
