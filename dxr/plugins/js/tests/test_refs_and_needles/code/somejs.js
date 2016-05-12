const stuff = require('stuff');

let foo = {
    print(x) {
        console.log(x);
    },
    echo() {
        function identity(y) {
            return y;
        }
        let identity2 = z => z;
        console.log(bar => identity(identity2(bar)));
    }
};

stuff.doStuff(foo);
