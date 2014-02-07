Exec {
    logoutput => on_failure,
}

import "dxr"

node default {
    include webapp::dxr
}
