pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'process_manager'

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)
conf.set('APP_ID', app_id)

configure_file(
  input: 'process-manager.in',
  output: 'process-manager',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

process_manager_sources = [
  '__init__.py',
  'constants.py',
  'main.py',
  'window.py',
  'process_manager.py',
  'ps_commands.py',
  'system_stats.py',
  'gpu_stats.py',
  'port_stats.py',
  'io_stats.py',
  'process_history.py',
  'alerts.py',
  'settings.py',
  'preferences.py',
]

install_data(process_manager_sources, install_dir: moduledir)

