%{

/** DXR Code Tokenizer for Sqlite Full Text Search 4
 * This is the lexer input for a custom sqlite fts4 tokenizer, if compiled with
 * -DTEST a simple main function will be compiled to test that the patterns
 * works as desired.
 *
 * To extent it just add patterns to in the rules section, and do your self the
 * favor of testing that it works afterwards. Enjoy...
 * Oh, and let try not to add tokens that might be present as something entirely
 * other than tokens in other languages.
 * IE. don't add [A-Z]-[a-z], as B-q is an expression and not a token is most languages.
 */

#include <stdbool.h>
#include <string.h>
#include <assert.h>

#include <sqlite3.h>

/** Location of a token in the source */
typedef struct DXRTokenLocation{
	int start, length;
} DXRTokenLocation;

/** DXR token actions (Quotation and Identifier requires normalization) */
typedef enum DXRTokenAction{
  ActionEnd         = 0,
  ActionQuote       = 1,
  ActionIdentifier  = 2,
  ActionOther       = 3
} DXRTokenAction;

/** Update location, MUST be invoked in EVERY rule, to keep track of location */
#define UPDATE_LOCATION			yyextra->start += yyextra->length; yyextra->length = yyleng

/** Overwrite the ECHO action so unmatched patterns from DXRCodeTokenizer is
 * printed to stderr, with a nice message.
 */
#define ECHO                do{                                                           \
                              fprintf(stderr, "DXRCodeTokenizer: Unhandled string: \"");  \
                              fwrite(yytext, yyleng, 1, stderr);                          \
                              fprintf(stderr, "\"\n");                                    \
                            }while(false)
%}

%option reentrant noyywrap nounput noinput
%option extra-type="DXRTokenLocation*"

%%
"-"                                 UPDATE_LOCATION; /* discard - is a search query modifier */
[a-zA-Z_]+[a-zA-Z_0-9]*             UPDATE_LOCATION; return ActionIdentifier;
"\""                                UPDATE_LOCATION; return ActionQuote;
[0-9]+("."[0-9]*)?                  UPDATE_LOCATION; return ActionOther;
"==="|"!=="                         UPDATE_LOCATION; return ActionOther;
"//"|"/*"|"*/"                      UPDATE_LOCATION; return ActionOther;
"&&"|"||"|"."|"->"|"=>"             UPDATE_LOCATION; return ActionOther;
"=="|"!="|"<="|">="|"<"|">"         UPDATE_LOCATION; return ActionOther;
"+="|"-="|"*="|"&="|"^="|"~="       UPDATE_LOCATION; return ActionOther;
"+"|"/"|"*"                         UPDATE_LOCATION; return ActionOther;
"("|")"|"["|"]"|"{"|"}"             UPDATE_LOCATION; return ActionOther;
"="|":"|";"|"."|"!"|\\|"$"|"@"      UPDATE_LOCATION; return ActionOther; 
"&"|"|"|"^"|"%"                     UPDATE_LOCATION; return ActionOther;
"~"|"#"|"?"                         UPDATE_LOCATION; return ActionOther;
".."|"--"|"<>"|"><"|","             UPDATE_LOCATION; return ActionOther;
.                                   UPDATE_LOCATION; /* discard */
"\n"                                UPDATE_LOCATION; /* discard */
%%

void
dxr_code_tokenizer_init(void);

#ifdef TEST

/** Test case structure for main */
typedef struct TestCase{
  /** Test text */
  char* text;
  /** Minimum and maximum number of tokens generated, -1 if not applicable */
  int   min, max;
  /** Second action to be returned, ActionEnd if not applicable */
  DXRTokenAction secondAction;
} TestCase;

#define TEST_SQL(msg, sql)          do{                                                           \
                                      if(verbose)                                                 \
                                        printf("%-35s sql = \"%s\"\n", msg, sql);                 \
                                      if(sqlite3_exec(db, sql, 0, 0, 0)){                         \
                                        fprintf(stderr, "SQLITE_ERROR: %s\n", sqlite3_errmsg(db));\
                                        return 1;                                                 \
                                      }                                                           \
                                    }while(false)

/* A basic main function to test the generated scanner */
int main(int argc, char* argv[]){
  // Read arguments
  bool verbose = false;
  int i;
  for(i = 1; i < argc; i++){
    if(strcmp(argv[i], "--verbose") == 0
       || strcmp(argv[i], "-v") == 0)
      verbose = true;
  }

  // List of test cases
  TestCase testcases[] = {
    // Text:                                  Min:   Max:   Second Action:
    {"Hello World",                             2,     2,   ActionEnd       },
    {"array[0] = 7+3+x1;",                      11,   11,   ActionEnd       },
    {"sda\"sdfdsf",                              3,    3,   ActionQuote     },
    {"33 identifier34c ?? -- ==",                5,    7,   ActionIdentifier},
    {"See how7his work",                         3,    3,   ActionEnd       },
    {"permissions.js",                           2,    3,   ActionEnd       },
    {NULL, 0, 0}
  };


  // Keep track of test failure
  bool failed = false;

  // Let's test the scanner, ie. that patterns are written correctly
  TestCase* testcase;
  for(testcase = testcases; testcase->text != NULL; testcase++){
  	yyscan_t scanner;
	  DXRTokenLocation loc;

    if(verbose)
      printf("--- Test string: \"%s\"\n", testcase->text);

    // Initialize scanner
  	loc.start = 0;
	  loc.length = 0;
  	yylex_init_extra(&loc, &scanner);

	  // Start scanning my text
	  YY_BUFFER_STATE b = yy_scan_string(testcase->text, scanner);
    DXRTokenAction action;
    int tokenCount = 0;
	  while((action = yylex(scanner)) != ActionEnd){
      // Test if this is secound token, and we didn't get the expected action
      if(tokenCount == 1
         && testcase->secondAction != ActionEnd
         && testcase->secondAction != action){
        failed = true;
        fprintf(stderr,
               "FAIL: Expected second token action %i,"
               " but got %i from string \"%s\" \n",
               testcase->secondAction, action, testcase->text);
      }
      // Print token, if requested
      if(verbose){
  	  	printf("start: %2i, length: %2i, string: \"", loc.start, loc.length);
	    	fwrite(testcase->text + loc.start, 1, loc.length, stdout);
	    	printf("\"\n");
      }
      tokenCount++;
	  }

	  // Release string buffer
	  yy_delete_buffer(b, scanner);

	  //Release scanner
	  yylex_destroy(scanner);

    // Check that we got the right number of tokens
    if(testcase->min != -1 && testcase->min > tokenCount){
      fprintf(stderr,
              "FAIL: Expected at least %i tokens,"
              "but got %i from string string \"%s\" \n",
              testcase->min, tokenCount, testcase->text);
      failed = true;
    }
    if(testcase->max != -1 && testcase->max < tokenCount){
      fprintf(stderr,
              "FAIL: Expected at most %i tokens,"
              "but got %i from string string \"%s\" \n",
              testcase->max, tokenCount, testcase->text);
      failed = true;
    }
  }

  // Time to test the tokenizer implementation in sqlite
  // Register tokenizer loading extension with sqlite
  dxr_code_tokenizer_init();

  // Open a test database, memory is fine
  sqlite3* db;
  if(verbose)
    printf("Open sqlite database\n");
  if(sqlite3_open(":memory:", &db)){
    fprintf(stderr, "SQLITE_ERROR: %s\n", sqlite3_errmsg(db));
    return 1;
  }

  // Let's call the tokenizer loading function
  TEST_SQL("Initialize tokenizer:",
           "SELECT initialize_tokenizer()");

  // Let's create an FTS4 table
  TEST_SQL("Create fts table:",
          "CREATE VIRTUAL TABLE fts USING fts4 (content, tokenize=dxrCodeTokenizer)");

  // Okay, time to insert something in the table
  // This will actually invoke the tokenizer
  // stuff could go wrong
  TEST_SQL("Insert into fts table",
           "INSERT INTO fts (rowid, content) "
           "VALUES (1, \"hello 'world' ju+st [testing].\")");

  TEST_SQL("Insert into fts table",
           "INSERT INTO fts (rowid, content) "
           "VALUES (2, \"permissions.js\")");

  TEST_SQL("Match in fts table",
           "SELECT rowid FROM fts WHERE content MATCH \"'permissions.js'\"");

  // Close the connection
  if(verbose)
    printf("Closing sqlite database\n");
  if(sqlite3_close(db)){
    fprintf(stderr, "SQLITE_ERROR: %s\n", sqlite3_errmsg(db));
    return 1;
  }

	return failed ? 1 : 0;
}

#endif

/** The sqlite extension starts here
 * Note: That tests will be broken if this appears before main
 */
#include <sqlite3ext.h>

#include "fts3_tokenizer.h"

SQLITE_EXTENSION_INIT1

/** DXR Code tokenizer context */
typedef struct DXRCodeTokenizer{
  /** Base class */
  sqlite3_tokenizer base;
  /**Case sensitivity for this tokenizer */
  bool              caseSensitive;
} DXRCodeTokenizer;

/** Size of static token allocation
 * Most tokens will fit in this allocation, and allocating it along with
 * DXRCodeCursor is cheap, a lot cheaper than allocating at each new token.
 */
#define STATIC_TOKEN_SIZE     255

/** DXR Code Cursor */
typedef struct DXRCodeCursor{
  /** Base class */
  sqlite3_tokenizer_cursor  base;
  /** Reentrant flex scanner context */
  yyscan_t                  scanner;
  /** Location variable for tracking flex */
  DXRTokenLocation          location;
  /** Buffer for the flex scanner */
  YY_BUFFER_STATE           buffer;
  /** Number of tokens returned */
  int                       position;
  /** Input buffer as given when opened */
  const char*               input;
  /** Static token memory for returning altered results */
  char                      staticToken[255];
  /** Dynamic token memory for returning altered results */
  char*                     dynamicToken;
} DXRCodeCursor;

/** Create a new tokenizer (defaults to case insensitive) */
static int
DXRCodeTokenizerCreate(int                argc,           /* Number of arguments */
                       const char* const  argv[],         /* Tokenizer arguments */
                       sqlite3_tokenizer  **ppTokenizer){ /* OUT: Created tokenizer */
  DXRCodeTokenizer *pTok;
  pTok = (DXRCodeTokenizer*)sqlite3_malloc(sizeof(DXRCodeTokenizer));
  if(!pTok)
    return SQLITE_NOMEM;
  memset(pTok, 0, sizeof(DXRCodeTokenizer));

  // Set case sensitivity
  pTok->caseSensitive = (argc > 0 && strcmp(argv[0], "case_sensitive") == 0);

  // Return the tokenizer
  *ppTokenizer = (sqlite3_tokenizer*)pTok;
  return SQLITE_OK;
}

/** Release a tokenizer */
static int
DXRCodeTokenizerDestroy(sqlite3_tokenizer* pTokenizer){
  DXRCodeTokenizer *pTok = (DXRCodeTokenizer*)pTokenizer;
  sqlite3_free(pTok);
  return SQLITE_OK;
}

/** Create DXRCodeCursor */
static int
DXRCodeTokenizerOpen(sqlite3_tokenizer*         pTokenizer, /* Tokenizer */
                     const char*                zInput,     /* Input */
                     int                        nInput,     /* Input length */
                     sqlite3_tokenizer_cursor** ppCursor){  /* OUT: Created cursor */
  DXRCodeCursor* pDXRCursor;
  if(nInput < 0)
    nInput = strlen(zInput);

  pDXRCursor = (DXRCodeCursor*)sqlite3_malloc(sizeof(DXRCodeCursor));
  if(!pDXRCursor)
    return SQLITE_NOMEM;
  memset(pDXRCursor, 0, sizeof(DXRCodeCursor));

  // Set input buffer
  pDXRCursor->input = zInput;

  // Set initial location
  pDXRCursor->location.start  = 0;
  pDXRCursor->location.length = 0;
  pDXRCursor->position        = 0;

  // Initialize scanner
  yylex_init_extra(&pDXRCursor->location, &pDXRCursor->scanner);
  pDXRCursor->buffer = yy_scan_bytes(zInput, nInput, pDXRCursor->scanner);

  // Set dynamic memory NULL
  pDXRCursor->dynamicToken = NULL;

  *ppCursor = (sqlite3_tokenizer_cursor*)pDXRCursor;
  return SQLITE_OK;
}

/** Release DXRCodeCursor */
static int
DXRCodeTokenizerClose(sqlite3_tokenizer_cursor* pCursor){
  DXRCodeCursor* pDXRCursor = (DXRCodeCursor*)pCursor;

  // Release scanner buffer
  yy_delete_buffer(pDXRCursor->buffer, pDXRCursor->scanner);

  // Release scanner
  yylex_destroy(pDXRCursor->scanner);

  // Free dynamic token allocation (if any)
  if(pDXRCursor->dynamicToken)
    sqlite3_free(pDXRCursor->dynamicToken);

  // Release the cursor
  sqlite3_free(pDXRCursor);

  return SQLITE_OK;
}

/** Normalized quotes, all quotes are normalized to this value
 * As having two different quotation marks is stupid when you
 * one of them is used in the search query language.
 * (ie. " is used for phrase search)
 */
static const char normalized_quote = '\'';

/** Fetch next token from cursor */
static int
DXRCodeTokenizerNext(sqlite3_tokenizer_cursor*  pCursor,      /* Cursor */
                     const char**               ppToken,      /* OUT: token text */
                     int*                       pnBytes,      /* OUT: token length */
                     int*                       piStartOffset,/* OUT: token start in text */
                     int*                       piEndOffset,  /* OUT: token end in text */
                     int*                       piPosition){  /* OUT: Position of token */
  DXRCodeCursor* pDXRCursor = (DXRCodeCursor*)pCursor;

  // Free dynamic token allocation (if any)
  if(pDXRCursor->dynamicToken)
    sqlite3_free(pDXRCursor->dynamicToken);
  pDXRCursor->dynamicToken = NULL;

  // Read next token, this gives us token action
  // and sets pDXRCursor->location
  DXRTokenAction ta = yylex(pDXRCursor->scanner);

  // If action is end, return
  if(ta == ActionEnd)
    return SQLITE_DONE;

  // Set return values from offset
  *piStartOffset  = pDXRCursor->location.start;
  *piEndOffset    = pDXRCursor->location.start + pDXRCursor->location.length;
  *piPosition     = pDXRCursor->position++;
  *pnBytes        = pDXRCursor->location.length;

  // Return a normalized qoutation mark if encountered
  // Notice that " will be for phrase search and ' for qouation
  // mark of any kind, in the search language.
  if(ta == ActionQuote){
    *ppToken = &normalized_quote;
    assert(*pnBytes == 1);
    return SQLITE_OK;
  }

  // Normalize to lower case if this is an identifier and the tokenizer has
  // setting case sensitive
  DXRCodeTokenizer *pTok = (DXRCodeTokenizer*)pDXRCursor->base.pTokenizer;
  if(ta == ActionIdentifier && !pTok->caseSensitive){
    // Use staticToken allocation if this is enought
    // else allocate some memory, just remember to store the allocation
    // in pDXRCursor->dynamicToken so it'll be released later.
    char* token = pDXRCursor->staticToken;
    if(*pnBytes > STATIC_TOKEN_SIZE){
      token = pDXRCursor->dynamicToken = (char*)sqlite3_malloc(*pnBytes);
      if(!token)
        return SQLITE_NOMEM;
    }

    // For each char if capital, make it lower
    int i;
    for(i = 0; i < *pnBytes; i++){
      char c = pDXRCursor->input[*piStartOffset + i];
      if('A' <= c && c <= 'Z')
        c = c - 'A' + 'a';
      token[i] = c;
    }
    
    // Return the normalized token
    *ppToken = token;
    return SQLITE_OK;
  }

  // Return token as is in buffer
  assert(ta == ActionOther || ta == ActionIdentifier);
  *ppToken = pDXRCursor->input + pDXRCursor->location.start;
  return SQLITE_OK;
}


/** Definition of the DXR code tokenizer module for sqlite */
static const sqlite3_tokenizer_module DXRCodeTokenizerModule = {
  0,                         /* iVersion */
  DXRCodeTokenizerCreate,    /* xCreate  */
  DXRCodeTokenizerDestroy,   /* xDestroy */
  DXRCodeTokenizerOpen,      /* xOpen    */
  DXRCodeTokenizerClose,     /* xClose   */
  DXRCodeTokenizerNext,      /* xNext    */
};


/* Implementation for the initialize_tokenizer() sqlite function,
 * creates and loads the code tokenizer so it's ready to use
 */
static void
initialize_tokenizer(sqlite3_context  *context,
                     int               argc,
                     sqlite3_value   **argv)
{
  const sqlite3_tokenizer_module *pTokenizer;
  sqlite3* db = sqlite3_context_db_handle (context);
  sqlite3_stmt *stmt;
  int rc;

  pTokenizer = &DXRCodeTokenizerModule;
  rc = sqlite3_prepare_v2(db, "SELECT fts3_tokenizer(?, ?)",
                          -1, &stmt, 0);

  if (rc != SQLITE_OK)
    {
      sqlite3_result_error_code (context, rc);
      return;
    }

  sqlite3_bind_text(stmt, 1, "dxrCodeTokenizer", -1, SQLITE_STATIC);
  sqlite3_bind_blob(stmt, 2, &pTokenizer, sizeof(pTokenizer), SQLITE_STATIC);
  sqlite3_step(stmt);
  rc = sqlite3_finalize(stmt);

  if (rc != SQLITE_OK)
    sqlite3_result_error_code (context, rc);
  else
    sqlite3_result_null (context);
}

/* Entry point for sqlite module initialization, extension
 * loading expects a function named like this. This function
 * creates the initialize_tokenizer() sqlite function, which
 * has to be called on a sqlite handle in order to initialize
 * a tokenizer instance for it.
 */
int
sqlite3_extension_init(sqlite3                     *db,
                       char                       **pzErrMsg,
                       const sqlite3_api_routines  *pApi)
{
  int rc;

  SQLITE_EXTENSION_INIT2(pApi)

  rc = sqlite3_create_function(db, "initialize_tokenizer", 0,
                               SQLITE_ANY,
                               NULL, initialize_tokenizer,
                               NULL, NULL);
  return rc;
}

/* Entry point for applications loading this module, it will enable
 * the loading of the sqlite module on each sqlite handle that's created.
 */
void
dxr_code_tokenizer_init (void)
{
  sqlite3_auto_extension ((void (*) (void)) sqlite3_extension_init);
}

