gnome = import('gnome')

bindir = join_paths(get_option('prefix'), get_option('bindir'))
service_conf = configuration_data()
service_conf.set('bindir', bindir)
configure_file(
  input: 'io.github.Pithos.service.in',
  output: 'io.github.Pithos.service',
  configuration: service_conf,
  install: true,
  install_dir: join_paths(get_option('datadir'), 'dbus-1/services')
)

pithos_resources = gnome.compile_resources('pithos',
  'io.github.Pithos.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir
)

install_data('io.github.Pithos.gschema.xml',
  install_dir: join_paths(get_option('datadir'), 'glib-2.0/schemas')
)

pithos_desktop = i18n.merge_file(
  input: 'io.github.Pithos.desktop.in',
  output: 'io.github.Pithos.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: join_paths(get_option('datadir'), 'applications')
)

pithos_appstream = i18n.merge_file(
  input: 'io.github.Pithos.appdata.xml.in',
  output: 'io.github.Pithos.appdata.xml',
  po_dir: '../po',
  install: true,
  install_dir: join_paths(get_option('datadir'), 'metainfo')
)

pithos_settings = gnome.compile_schemas()

appstream_util = find_program('appstream-util', required: false)
if appstream_util.found()
  test('Validate appstream file', appstream_util,
    args: ['validate', pithos_appstream]
  )
endif

desktop_utils = find_program('desktop-file-validate', required: false)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils,
    args: [pithos_desktop]
  )
endif

compile_schemas = find_program('glib-compile-schemas', required: false)
if compile_schemas.found()
  test('Validate schema file', compile_schemas,
    args: ['--strict', '--dry-run', meson.current_source_dir()]
  )
endif

gtk_builder_tool = find_program('gtk-builder-tool', required: false)
if gtk_builder_tool.found()
  ui_files = [
    ['ui', 'AboutPithosDialog.ui'],
    ['ui', 'PithosWindow.ui'],
    ['ui', 'PreferencesPithosDialog.ui'],
    ['ui', 'SearchDialog.ui'],
    ['ui', 'StationsDialog.ui'],
    ['ui', 'EqDialog.ui'],
    ['gtk', 'help-overlay.ui'],
    ['gtk', 'menus.ui'],
  ]
  foreach ui_file : ui_files
    test('Validate @0@'.format(ui_file[1]), gtk_builder_tool,
      args: ['validate', join_paths(meson.current_source_dir(), ui_file[0], ui_file[1])]
    )
  endforeach
endif

subdir('icons')
