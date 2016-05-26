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

class Guy {
    constructor(name) {
        this.name = name;
        this.fun = function thathasaname() {
            return 4 - name;
        };
    }

    static greet(other) {
        return "HI " + other;
    }

    get name() {
        return this.name;
    }

    doIt(woof) {
        console.log(woof + this.name);
    }
}

class Bob extends Guy {
    doIt(woof) {
        this.name = woof;
    }
}

let him = new Bob("Abe");
Guy.greet("Joe");
him.doIt("Jef");
him.name.toString();
