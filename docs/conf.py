import os
import sys

project = 'PyRAF'
release = '2.2'
version = '.'.join(release.split('.')[:2])

master_doc = 'index'
extensions = [
    'sphinx.ext.intersphinx',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.extlinks',
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
}

html_theme = "bootstrap-astropy"
html_theme_options = {
    'logotext1': 'IRAF',
    'logotext2': 'PyRAF',
    'logotext3': ':docs',
    'astropy_project_menubar': False
}
html_static_path = ['_static']

# These paths are either relative to html_static_path
# or fully qualified paths (eg. https://...)
html_css_files = [
    'brand.css',
]
