"use strict";

const node_modules = '../../../tooling/node/node_modules/'
const should = require(node_modules + 'chai').should();
const dxr = require('../dxr.js');
const instance = dxr.instance();

describe('Context menu dismiss tests', function() {
    const url = "http://127.0.0.1:8000/code/source/fixed_ref.h";
    // Coordinates of a variable to click on:
    const varLocX = 200;
    const varLocY = 120;

    before(function(done) {
        instance.serve(__dirname, done, this);
    });

    it('should dismiss when left clicked', function(done) {
        dxr.openPage(instance.browser, url, function(err, page) {
            // Click on a variable name:
            page.sendEvent('click', varLocX, varLocY, function() {
                // Check that the click resulted in a context menu:
                dxr.hasContextMenu(page, function(err, hasMenu) {
                    hasMenu.should.equal(true);
                    // Click on the context menu to load results:
                    page.sendEvent('click', varLocX + 10, varLocY + 10, function() {
                        page.goBack(function() {
                            // Check that there's no longer a context menu:
                            dxr.hasContextMenu(page, function(err, hasMenu) {
                                hasMenu.should.equal(false);
                                page.close();
                                done();
                            });
                        });
                    });
                });
            });
        });
    });

    it('should dismiss on an outside click', function(done) {
        dxr.openPage(instance.browser, url, function(err, page) {
            // Click on a variable name:
            page.sendEvent('click', varLocX, varLocY, function() {
                // Check that the click resulted in a context menu:
                dxr.hasContextMenu(page, function(err, hasMenu) {
                    hasMenu.should.equal(true);
                    // Click outside the context menu:
                    page.sendEvent('click', 10, 10, function() {
                        // Check that there's no longer a context menu:
                        dxr.hasContextMenu(page, function(err, hasMenu) {
                            hasMenu.should.equal(false);
                            page.close();
                            done();
                        });
                    });
                });
            });
        });
    });

    after(function(done) {
        instance.stop(done);
    });
});
