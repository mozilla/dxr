from os.path import splitext

from funcy import ichunks
from binaryornot.helpers import is_binary_string
from chardet.universaldetector import UniversalDetector


def icon(path, is_binary=False):
    """Return the basename (no extension) of the icon file to use for a path."""
    root, ext = splitext(path)
    class_name = ext_map.get(ext[1:], 'unknown')
    if is_binary and class_name != 'image':
        return 'binary'
    return class_name


def decode_data(data, encoding_guess, can_be_binary=True):
    """Given string data, return an (is_text, data) tuple, where data is
    returned as unicode if we think it's text and were able to determine an
    encoding for it.
    If can_be_binary is False, then skip the initial is_binary check.
    """
    if not (can_be_binary and is_binary_string(data[:1024])):
        try:
            # Try our default encoding.
            data = data.decode(encoding_guess)
            return True, data
        except UnicodeDecodeError:
            # Fall back to chardet - chardet is really slow, which is why we
            # don't just do chardet from the start.
            detector = UniversalDetector()
            for chunk in ichunks(80, data):
                detector.feed(chunk)
                if detector.done:
                    break
            detector.close()
            if detector.result['encoding']:
                try:
                    data = data.decode(detector.result['encoding'])
                    return True, data
                except (UnicodeDecodeError, LookupError):
                    # Either we couldn't decode or chardet gave us an encoding
                    # that python doesn't recognize (yes, it can do that).
                    pass  # Leave data as str.
    return False, data


def is_binary_image(path):
    """Return whether the path points to an image without human-readable
    contents."""
    return icon(path) == 'image'


def is_textual_image(path):
    """Return whether the path points to an image with text contents."""
    return icon(path) == 'svg'


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
    "SVG":        'svg',
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
    "vsprops":    'vs',
    "jpg":        'image',
    "jpeg":       'image',
    "png":        'image',
    "gif":        'image'
}
