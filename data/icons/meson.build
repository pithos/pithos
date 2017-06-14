themes = [
  ['hicolor', [
    ['48x48', [
      'io.github.Pithos-tray.png'
    ]],
    ['scalable', [
      'io.github.Pithos-tray.svg',
      'io.github.Pithos.svg'
    ]],
    ['symbolic', [
      'io.github.Pithos-symbolic.svg'
    ]]
  ]],
  ['ubuntu-mono-dark', [
    ['16x16', [
      'io.github.Pithos-tray.svg'
    ]]
  ]],
  ['ubuntu-mono-light', [
    ['16x16', [
      'io.github.Pithos-tray.svg'
    ]]
  ]]
]

foreach i : themes
  theme = i[0]
  sizes = i[1]
  foreach i : sizes
    size = i[0]
    icons = i[1]
    foreach icon : icons
      install_data('@0@/@1@/apps/@2@'.format(theme, size, icon),
        install_dir: '@0@/icons/@1@/@2@/apps'.format(get_option('datadir'), theme, size)
      )
    endforeach
  endforeach
endforeach
