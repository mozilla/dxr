var templateFiles = [
    'dxr/static/templates/partial/promoted.html',
    'dxr/static/templates/partial/results_container.html',
    'dxr/static/templates/partial/result_separator.html',
    'dxr/static/templates/partial/results.html',
    'dxr/static/templates/partial/result_lines.html',
    'dxr/static/templates/partial/switch_tree.html',
    'dxr/static/templates/partial/results_header.html',
    'dxr/static/templates/context_menu.html',
    'dxr/static/templates/path_line.html',
];

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
        nunjucks: {
            precompile: {
                baseDir: 'dxr/static/templates/',
                src: templateFiles,
                dest: 'dxr/static/js/templates.js',
                options: {
                    name: function(filename) {
                        var re = /(partial\/)?(|\w+.\w{4})$/g;
                        return re.exec(filename)[0];
                    }
                }
            }
        },
        jshint: {
            all: ['Gruntfile.js', 'dxr/static/js/*.js']
        },
        watch: {
            nunjucks: {
                files: templateFiles,
                tasks: ['nunjucks']
            }
        }
    });

    grunt.loadNpmTasks('grunt-contrib-jshint');
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.loadNpmTasks('grunt-uncss');
    grunt.loadNpmTasks('grunt-nunjucks');

    grunt.registerTask('dev', ['nunjucks', 'watch']);
    grunt.registerTask('lint', ['jshint', 'uncss:dev']);

    grunt.registerTask('precompile', ['nunjucks']);
};
