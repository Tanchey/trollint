
import jinja2 as j2
import os
import sys
from progressbar import progressbar


def load_template(filename):

    abs_path = os.path.join(os.path.dirname(sys.argv[0]),
            'templates', filename)

    with open(abs_path) as fi:
        template = j2.Template(fi.read())

    return template


def render_to_directory(dirname, title, files, category_names):

    try:
        os.mkdir(dirname)
    except OSError:
        pass

    index_template = load_template('report_index.jinja')
    single_file_template = load_template('report_single_file.jinja')

    with open(os.path.join(dirname, 'index.html'), 'w') as fo:
        fo.write(index_template.render(files=files,
                               diagnostic_categories=category_names,
                               title=title).encode('utf8'))

    for f in progressbar(files):
        for dname, ds in f['diagnostic_groups'].iteritems():
            path = os.path.join(dirname, f['name'].replace('/', '_'))
            path += '_' + dname + '.html'

            text = single_file_template.render(filename=f['name'],
                                   diagnostics=ds)
            with open(path, 'w') as fo:
                fo.write(text.encode('utf8'))
