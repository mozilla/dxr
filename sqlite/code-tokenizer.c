#include <sqlite3ext.h>
#include "fts3_tokenizer.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sqlite3.h>

#define FALSE 0
#define TRUE !FALSE

SQLITE_EXTENSION_INIT1

typedef struct MxrCodeTokenizer MxrCodeTokenizer;
typedef struct MxrCodeCursor MxrCodeCursor;

enum
{
  PARSER_STATE_BLANK,
  PARSER_STATE_TOKEN,
  PARSER_STATE_NUMBER
};

struct MxrCodeTokenizer
{
  sqlite3_tokenizer base;
};

struct MxrCodeCursor
{
  sqlite3_tokenizer_cursor base;

  const char *parsed_string;
  const char *cursor;

  char *token;
  int allocated_token_len;

  unsigned int parsed_string_len;
  unsigned int current_token_cursor;
  unsigned int current_word_start;
  unsigned int current_word_end;
  unsigned int position;

  unsigned int split_word : 1;
  unsigned int state      : 3;
};

/*
** Create a new tokenizer instance.
*/
static int
dxrCodeTokenizerCreate(int                 argc,        /* Number of entries in argv[] */
		       const char * const *argv,        /* Tokenizer creation arguments */
		       sqlite3_tokenizer **ppTokenizer) /* OUT: Created tokenizer */
{
  MxrCodeTokenizer *p;

  p = (MxrCodeTokenizer *)sqlite3_malloc(sizeof(MxrCodeTokenizer));

  if (!p)
    return SQLITE_NOMEM;

  memset(p, 0, sizeof(MxrCodeTokenizer));
  *ppTokenizer = (sqlite3_tokenizer *)p;

  return SQLITE_OK;
}

/*
** Destroy a tokenizer
*/
static int
dxrCodeTokenizerDestroy(sqlite3_tokenizer *pTokenizer)
{
  MxrCodeTokenizer *p = (MxrCodeTokenizer *)pTokenizer;
  sqlite3_free(p);
  return SQLITE_OK;
}

/*
** Prepare to begin tokenizing a particular string.  The input
** string to be tokenized is pInput[0..nBytes-1].  A cursor
** used to incrementally tokenize this string is returned in 
** *ppCursor.
*/
static int
dxrCodeTokenizerOpen(sqlite3_tokenizer         *pTokenizer, /* The tokenizer */
                     const char                *zInput,     /* Input string */
                     int                        nInput,     /* Length of zInput in bytes */
                     sqlite3_tokenizer_cursor **ppCursor)   /* OUT: Tokenization cursor */
{
  MxrCodeCursor *pCsr;

  if (nInput<0)
    nInput = strlen(zInput);

  pCsr = (MxrCodeCursor *)sqlite3_malloc(sizeof(MxrCodeCursor));
  memset(pCsr, 0, sizeof(MxrCodeCursor));
  pCsr->parsed_string = pCsr->cursor = zInput;
  pCsr->parsed_string_len = nInput;
  pCsr->state = PARSER_STATE_BLANK;

  *ppCursor = (sqlite3_tokenizer_cursor *)pCsr;

  return SQLITE_OK;
}

/*
** Close a tokenization cursor.
*/
static int
dxrCodeTokenizerClose(sqlite3_tokenizer_cursor *pCursor)
{
  MxrCodeCursor *pCsr = (MxrCodeCursor *)pCursor;

  sqlite3_free(pCsr->token);
  sqlite3_free(pCsr);

  return SQLITE_OK;
}

/*
** Extract the next token from a tokenization cursor.
*/
static int
dxrCodeTokenizerNext(sqlite3_tokenizer_cursor  *pCursor,       /* Cursor returned by simpleOpen */
                     const char               **ppToken,       /* OUT: *ppToken is the token text */
                     int                       *pnBytes,       /* OUT: Number of bytes in token */
                     int                       *piStartOffset, /* OUT: Starting offset of token */
                     int                       *piEndOffset,   /* OUT: Ending offset of token */
                     int                       *piPosition)    /* OUT: Position integer of token */
{
  MxrCodeCursor *pCsr = (MxrCodeCursor *)pCursor;
  const char *cursor;

  if (pCsr->split_word)
    {
      int i, start;

      start = pCsr->current_token_cursor;

      for (i = pCsr->current_token_cursor + 1; i <= pCsr->current_word_end; i++)
        {
          if (i == pCsr->current_word_end ||
              pCsr->parsed_string[i] == '_' ||
              (isupper (pCsr->parsed_string[i]) &&
               !isupper (pCsr->parsed_string[i - 1])))
            {
              *pnBytes = i - pCsr->current_token_cursor + 1;
              *piStartOffset = pCsr->current_token_cursor;
              *piEndOffset = i;
              *piPosition = pCsr->position;

              *ppToken = &pCsr->token[pCsr->current_token_cursor - start];

              pCsr->current_token_cursor = i;
              pCsr->position++;

              return SQLITE_OK;
            }
        }

      if (i >= pCsr->current_word_end)
        pCsr->split_word = FALSE;
    }

  if (pCsr->cursor >= &pCsr->parsed_string[pCsr->parsed_string_len])
    return SQLITE_DONE;

  while (pCsr->cursor <= &pCsr->parsed_string[pCsr->parsed_string_len])
    {
      cursor = pCsr->cursor;

      if (!isalnum (*cursor) && *cursor != '_')
        {
          if (pCsr->state == PARSER_STATE_TOKEN)
            pCsr->current_word_end = cursor - pCsr->parsed_string - 1;

          if ( pCsr->state == PARSER_STATE_TOKEN )
            {
              int token_len, i;

              *pnBytes = pCsr->current_word_end - pCsr->current_word_start + 1;
              *piStartOffset = pCsr->current_word_start;
              *piEndOffset = pCsr->current_word_end + 1;
              *piPosition = pCsr->position;

              token_len = *piEndOffset - *piStartOffset;

              if (token_len > pCsr->allocated_token_len)
                {
                  char *str;

                  pCsr->allocated_token_len = token_len + 32;
                  str = sqlite3_realloc(pCsr->token, pCsr->allocated_token_len);

                  if (!str)
                    return SQLITE_NOMEM;

                  pCsr->token = str;
                }

              for (i=0; i<token_len;i++)
                {
                  char c = pCsr->parsed_string[*piStartOffset + i];

                  if (c >= 'A' && c <= 'Z')
                    c = c - 'A' + 'a';

                  pCsr->token[i] = c;
                }

              *ppToken = pCsr->token;

              pCsr->state = PARSER_STATE_BLANK;
              pCsr->position++;
              pCsr->cursor++;

              return SQLITE_OK;
            }

          pCsr->state = PARSER_STATE_BLANK;
          pCsr->split_word = FALSE;
        }
      else if (isdigit (*cursor))
        {
          if (pCsr->state != PARSER_STATE_TOKEN)
            pCsr->state = PARSER_STATE_NUMBER;
        }
      else if (pCsr->state == PARSER_STATE_BLANK &&
               (isalpha (*cursor) || *cursor == '_'))
        {
          pCsr->state = PARSER_STATE_TOKEN;
          pCsr->current_word_start = pCsr->current_word_end = cursor - pCsr->parsed_string;
        }
      else if (pCsr->state == PARSER_STATE_TOKEN &&
               (isalnum (*cursor) || *cursor == '_'))
        {
          if ( *cursor == '_'  ||
               (isalpha (*cursor) && isalpha (* (cursor - 1)) &&
                isupper (*cursor) && !isupper (* (cursor - 1))))
            {
              pCsr->split_word = TRUE;
              pCsr->current_token_cursor = pCsr->current_word_start;
            }

          pCsr->current_word_end = cursor - pCsr->parsed_string;
        }

      pCsr->cursor++;
    }

  if (pCsr->cursor >= &pCsr->parsed_string[pCsr->parsed_string_len])
    return SQLITE_DONE;

  return SQLITE_OK;
}

/*
** The set of routines that implement the simple tokenizer
*/
static const sqlite3_tokenizer_module mxrCodeTokenizerModule = {
  0,                           /* iVersion */
  dxrCodeTokenizerCreate,      /* xCreate  */
  dxrCodeTokenizerDestroy,     /* xDestroy */
  dxrCodeTokenizerOpen,        /* xOpen    */
  dxrCodeTokenizerClose,       /* xClose   */
  dxrCodeTokenizerNext,        /* xNext    */
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

  pTokenizer = &mxrCodeTokenizerModule;
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
