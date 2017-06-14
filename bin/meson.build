prefix = get_option('prefix')

cdata = configuration_data()
cdata.set('VERSION', meson.project_version())
cdata.set('localedir', join_paths(prefix, get_option('localedir')))
cdata.set('pkgdatadir', join_paths(prefix, pkgdatadir))

configure_file(
  input: 'pithos.in',
  output: 'pithos',
  configuration: cdata,
  install: true,
  install_dir: get_option('bindir')
)

pithos = join_paths(meson.build_root(), 'bin/pithos')
run_target('run',
  command: [pithos, '-v'],
  depends: [
    pithos_resources,
    pithos_settings
  ]
)
