# Settings, will be filled out by ./dxr-build -f FILE --server
# See create_server() in dxr-build.py

trees                 = ${trees}
wwwroot               = ${wwwroot}
template_parameters   = ${template_parameters}
generated_date        = ${generated_date}

# The right hand side of assignments above will be filled using the string.Template
# function builtin to python. Using repr, we save simple variables this way for
# use later. Essentially, this means that we don't do parser config files on
# the server, which is nice and more speed.
