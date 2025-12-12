project('process-manager',
  version: '1.0.0',
  meson_version: '>= 0.59.0',
  default_options: [
    'warning_level=2',
    'werror=false',
  ],
)

# Application ID
app_id = 'io.github.processmanager.ProcessManager'

# Dependencies
python = import('python')
python_installation = python.find_installation('python3')

dependency('glib-2.0', version: '>= 2.66')
dependency('gtk4', version: '>= 4.6')
dependency('libadwaita-1', version: '>= 1.2')
dependency('pygobject-3.0', version: '>= 3.42')

# Directories
prefix = get_option('prefix')
bindir = prefix / get_option('bindir')
datadir = prefix / get_option('datadir')
pkgdatadir = datadir / meson.project_name()
moduledir = pkgdatadir / 'process_manager'

# i18n
i18n = import('i18n')
gnome = import('gnome')

# Subdirectories
subdir('data')
subdir('src')
subdir('po')

gnome.post_install(
  glib_compile_schemas: true,
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)

