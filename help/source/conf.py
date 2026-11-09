# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Michał Kozdronkiewicz @ wmk
"""Sphinx configuration for NetAnal documentation."""

import sys, os

extensions = ['sphinx.ext.todo', 'sphinx.ext.imgmath', 'sphinx.ext.viewcode']

templates_path = ['_templates']

source_suffix = '.rst'

master_doc = 'index'

project = u'NetAnal'
copyright = u'2026, Michał Kozdronkiewicz @ wmk'

version = '0.1'
release = '0.1'

exclude_patterns = []

pygments_style = 'sphinx'

html_theme = 'default'

html_static_path = ['_static']

htmlhelp_basename = 'NetAnaldoc'

latex_documents = [
  ('index', 'NetAnal.tex', u'NetAnal Documentation',
   u'Michał Kozdronkiewicz @ wmk', 'manual'),
]

man_pages = [
    ('index', 'NetAnal', u'NetAnal Documentation',
     [u'Michał Kozdronkiewicz @ wmk'], 1)
]
