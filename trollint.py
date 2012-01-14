#!/usr/bin/env python
# encoding: utf-8

import os
import sys
import clang.cindex as cindex
import config
import passes.base.pass_base
from progressbar import progressbar
from diagnostic import from_clang_diagnostic
import report
from itertools import groupby
from utils import get_clang_args, unique, get_clang_analyzer_diagnostics


def discover_pass_classes():
    import imp
    passes_dir = os.path.join(os.path.dirname(sys.argv[0]), 'passes')
    module_names = [f for f in os.listdir(passes_dir)
                         if f.endswith('.py') and f != '__init__.py']
    modules = [imp.load_source('passes.' + m.replace('.py', ''),
                            os.path.join(passes_dir, m)) for m in module_names]

    def extract(m):
        result = []
        for maybe_class_name in dir(m):
            if 'Base' in maybe_class_name:
                continue
            maybe_class = getattr(m, maybe_class_name)
            if isinstance(maybe_class, type)\
                   and issubclass(maybe_class, passes.base.pass_base.PassBase):
                result.append(maybe_class)
        return result

    return sum([extract(m) for m in modules], [])


def lint_one_file(filename, pass_classes, clang_args):

    try:
        with open(filename) as fi:
            blob = fi.read()
    except IOError:
        print('Could not open file {0}'.format(filename))
        return []

    index = cindex.Index.create()
    parse_opts = cindex.TranslationUnit.PrecompiledPreamble

    tu = index.parse(filename, clang_args, options=parse_opts)

    local_cursors = [c for c in tu.cursor.get_children()\
            if c.location.file and not os.path.isabs(c.location.file.name)
               and not c.location.file.name.startswith('opt')
               and not c.location.file.name.startswith('./opt')]

    diags = []

    # get clang compiler diagnostics
    diags += [from_clang_diagnostic(d, filename) for d in tu.diagnostics]

    # get clang analyzer diagnostics
    diags += get_clang_analyzer_diagnostics(filename, clang_args)

    for pass_class in pass_classes:

        p = pass_class()

        if not p.enabled:
            continue

        if 'config' in pass_class.needs:
            p.config = config.Config()

        if 'cursors' in pass_class.needs:
            p.cursors = local_cursors

        if 'text' in pass_class.needs:
            p.text = blob

        if 'filename' in pass_class.needs:
            p.filename = filename

        diags += p.get_diagnostics()

    return diags


def lint_files(filenames, pass_classes, clang_args):

    diags = []

    for filename in progressbar(filenames):
        diags += lint_one_file(filename, pass_classes, clang_args)

    def interesting_file(d):
        if os.path.isabs(d.filename):
            return False

        if d.filename.startswith('opt') or d.filename.startswith('./opt'):
            return False

        return True

    diags = filter(interesting_file, diags)

    diags = sorted(diags, key=lambda d: d.line_number)
    diags = sorted(diags, key=lambda d: d.filename)

    return unique(diags)

if __name__ == '__main__':

    filenames = sys.argv[1:]

    pass_classes = discover_pass_classes()

    clang_args = get_clang_args()

    diags = lint_files(filenames, pass_classes, clang_args)

    category_names = list(set([d.category for d in diags]))

    def group_diagnostics(ds):

        def file_from_group(g):
            name = g[0]

            categories = {}
            for cname in category_names:
                categories[cname] = []

            for cat, ds in groupby(g[1], lambda d: d.category):
                if cat in categories:
                    categories[cat] += list(ds)
                else:
                    categories[cat] = list(ds)
            return {'name': name, 'diagnostic_groups': categories}

        result = [file_from_group(g) for g
                    in groupby(ds, lambda d: d.filename)]
        return result

    files_with_categorized_diags = group_diagnostics(diags)

    report.render_to_directory('report', 'OHai',
            files_with_categorized_diags, category_names)

    if not diags:
        print('all clear')
