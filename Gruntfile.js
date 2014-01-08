module.exports = function(grunt) {

    grunt.initConfig({
        uncss: {
            dev: {
                files: {
                    'dxr/static/css/dist/dxr.css': [
                        'dxr/templates/*.html',
                        'dxr/templates/partial/*.html'
                    ]
                },
                options: {
                    stylesheets: [
                        'dxr/static/css/dxr.css',
                        'dxr/static/css/code-style.css'
                    ]
                }
            }
        },
        jshint: {
            all: ['Gruntfile.js', 'dxr/static/js/*.js']
        }
    });

    grunt.loadNpmTasks('grunt-uncss');
    grunt.loadNpmTasks('grunt-contrib-jshint');

    grunt.registerTask('dev', ['jshint', 'uncss:dev']);
};
