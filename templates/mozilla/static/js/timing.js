function printRequestTime() {
    var url = window.location.href;
    var pattern = /request_time=(\d+)/;
    var initial = url.match (pattern);
    var date = new Date ();

    document.write ((date.getTime () - RegExp.$1) / 1000);
    document.write ("s");
}
