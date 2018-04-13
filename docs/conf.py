import os
import sys
import time
import datetime
import subprocess

rootpath = os.path.abspath('../')
sys.path.insert(0, rootpath)

from mock import Mock
sys.modules['fcntl'] = Mock()
sys.modules['pycurl'] = Mock()
import fcntl
import pycurl
import motioneye

extensions = [
  'sphinx.ext.autodoc',
  'sphinx.ext.autosummary',
  'sphinx.ext.todo',
]

project = u'Motioneye'
copyright = u'2013 Calin Crisan'
version = motioneye.VERSION

add_module_names = False
autodoc_member_order='groupwise'
autodoc_mock_imports = ['fcntl', 'pycurl']
autodoc_default_flags = ['members','private-members','undoc-members']
autosummary_generate = True

exclude_patterns = ['_build' ]

html_theme = "sphinx_rtd_theme"
html_theme_path = ["_themes", ]
html_theme_options = {
    'canonical_url': '',
    'analytics_id': '',
    'logo_only': True,
    'display_version': False
}

html_title = "Motioneye %s" % (version)
html_logo = '../extra/motioneye-64x64.png'
html_short_title = "Motioneye v%s documentation " % (version)
html_domain_indices = True
html_use_index = True
html_split_index = True
html_show_sourcelink = False
htmlhelp_basename = 'meyedoc'

master_doc = 'index'
modindex_common_prefix = ['motioneye.']


def run_apidoc():
    cur_dir = os.path.abspath(os.path.dirname(__file__))
    package_path = os.path.abspath(os.path.dirname(cur_dir))
    output_path = os.path.join(cur_dir, 'api')
    cmd_path = 'sphinx-apidoc'
    if hasattr(sys, 'real_prefix'):
        d = os.listdir(sys.prefix)
    else:
        d = os.listdir(os.path.dirname(sys.executable))
    for folder in ['bin', 'Scripts']:
        if folder in d:
            cmd_path = os.path.abspath(os.path.join(sys.prefix, folder, 'sphinx-apidoc'))
    print("sphinx apidoc read %s" % (package_path) )
    print("sphinx apidoc write %s" % (output_path) )
    print("Execute %s" % cmd_path)
    subprocess.check_call([cmd_path, '--force', '--separate', '-o', output_path, package_path])


run_apidoc()   
