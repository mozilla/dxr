from os.path import splitext

# Current implementation is very simple, if utf-8 decoding works we declare it
# text, otherwise we say it's binary.
# To find an icon we file extension, ultimately we use libmagic and resolve
# mimetypes to icons.

def icon(path):
    root, ext = splitext(path)
    return "mimetypes/" + ext_map.get(ext[1:], "unknown")


def is_text(path, data):
    # Simple stupid test that apparently works rather well :)
    return '\0' not in data


# File extension known as this point
ext_map = {
    "html":       'html',
    "xhtml":      'html',
    "htm":        'html',
    "js":         'js',
    "h":          'h',
    "hpp":        'h',
    "cpp":        'cpp',
    "cc":         'cpp',
    "cxx":        'cpp',
    "c":          'c',
    "xul":        'ui',
    "svg":        'svg',
    "in":         'build',
    "idl":        'conf',
    "java":       'java',
    "xml":        'xml',
    "py":         'py',
    "css":        'css',
    "mk":         'build',
    "txt":        'txt',
    "sh":         'sh',
    "ini":        'conf',
    "properties": 'conf',
    "dtd":        'xml',
    "patch":      'diff',
    "asm":        'asm',
    "jsm":        'js',
    "cfg":        'conf',
    "m4":         'conf',
    "webidl":     'conf',
    "vcproj":     'vs',
    "vcxproj":    'vs',
    "xsl":        'xml',
    "hxx":        'h',
    "sln":        'vs',
    "diff":       'diff',
    "cs":         'cs',
    "iso":        'iso',
    "php":        'php',
    "rb":         'rb',
    "ipdl":       'conf',
    "mm":         'mm',
    "tex":        'tex',
    "vsprops":    'vs'
}
