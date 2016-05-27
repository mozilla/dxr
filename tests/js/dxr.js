'use strict';

const exec = require('child_process').exec;
const node_modules = '../../tooling/node/node_modules/';
const sync_exec = require(node_modules + 'sync-exec');
const sleep = require(node_modules + 'sleep');
const driver = require(node_modules + 'node-phantom-simple');
const phantomPath = require(node_modules + 'phantomjs').path;
const Promise = require(node_modules + 'promise');

// Return an object representing a browser/index instance.
function instance() {
    return {
        'browser': null,  // the browser object
        // Create a browser object and store it on us, and index and
        // serve dir.  Calls done() when finished.
        'serve': function(dir, done, context) {
            const self = this;
            // Increase the done() timeout so we can start dxr serve:
            context.timeout(5000);
            const browserPromise = new Promise(function(resolve, reject) {
                driver.create({ path: phantomPath }, function(err, browser) {
                    resolve(browser);
                });
            });
            const servePromise = new Promise(function(resolve, reject) {
                process.chdir(dir);
                sync_exec('dxr index');
                const server = exec('dxr serve -a');
                server.stderr.once('data', function (data) {
                    resolve('served');
                });
            });
            Promise.all([browserPromise, servePromise])
                .then(function (res) {
                    self.browser = res[0];
                    // Phooey, a little more wait seems to be necessary for
                    // serve to actually be ready.
                    sleep.sleep(1);
                    done();
                });
        },
        'stop': function(done) {
            exec("pkill -f 'dxr serve -a'");
            exec("curl -XDELETE 'http://localhost:9200/dxr_test_*'");
            // (Putting a 'done' in the call to exit causes slimer
            // to quit where it otherwise doesn't ... for reasons.)
            this.browser.exit(done);
        }
    };
}

// Return (err, page) to callback, where url has been loaded in page and
// page has been resized to width x height.
function openPage(browser, url, callback, width, height) {
    browser.createPage(function(err, page) {
        if (err) {
            callback(err, page);
        }
        page.open(url, function (err, status) {
            if (err) {
                callback(err, page);
            }
            width = width || 1024;
            height = height || 768;
            page.set('viewportSize', { width: width, height: height }, function() {
                callback(err, page);
            });
        });
    });
}

// Return (err, hasMenu) to callback, where hasMenu is true if page
// currently has an open context menu.
function hasContextMenu(page, callback) {
    page.evaluate(
        function() {
            return $('#context-menu').length === 1;
        },
        callback)
}

module.exports = {
    instance: instance,
    openPage: openPage,
    hasContextMenu: hasContextMenu
};
