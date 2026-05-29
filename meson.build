project('pithos',
  version: '1.6.3',
  meson_version: '>= 0.50.0'
)

i18n = import('i18n')
pkgdatadir = join_paths(get_option('datadir'), meson.project_name())

install_subdir(
  'pithos',
  install_dir: pkgdatadir,
  exclude_directories: [
    '__pycache__',
    'pandora/__pycache__',
    'plugins/__pycache__',
    'plugins/dbus_util/__pycache__'
  ]
)
subdir('data')
subdir('bin')
subdir('docs')
subdir('po')

meson.add_install_script('meson_post_install.py')
