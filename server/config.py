# Settings, will be filled out by ./dxr-build -f FILE --server
# See create_server() in dxr-build.py

TREES                 = ${trees}
WWW_ROOT              = ${wwwroot}
TEMPLATE_PARAMETERS   = ${template_parameters}
GENERATED_DATE        = ${generated_date}

# The right hand side of assignments above will be filled using the string.Template
# function builtin to python. Using repr, we save simple variables this way for
# use later. Essentially, this means that we don't do parser config files on
# the server, which is nice and more speed.
