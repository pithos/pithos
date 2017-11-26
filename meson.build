project('pithos',
  version: '1.4.1',
  meson_version: '>= 0.40.0'
)

i18n = import('i18n')
pkgdatadir = join_paths(get_option('datadir'), meson.project_name())

install_subdir('pithos', install_dir: pkgdatadir)
subdir('data')
subdir('bin')
subdir('docs')
subdir('po')

meson.add_install_script('meson_post_install.py')
