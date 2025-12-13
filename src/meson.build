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
  'settings.py',
  'preferences.py',
  'utils.py',
]

# Dialog classes
dialogs_sources = [
  'dialogs/__init__.py',
  'dialogs/process_details.py',
  'dialogs/renice.py',
  'dialogs/export.py',
  'dialogs/shortcuts.py',
  'dialogs/termination.py',
]

# Tab mixin classes
tabs_sources = [
  'tabs/__init__.py',
  'tabs/gpu_tab.py',
  'tabs/ports_tab.py',
]

# UI panel mixin classes
ui_sources = [
  'ui/__init__.py',
  'ui/stats_bar.py',
  'ui/selection_panel.py',
  'ui/bookmarks_panel.py',
  'ui/high_usage_panel.py',
]

# Handler mixin classes
handlers_sources = [
  'handlers/__init__.py',
  'handlers/keyboard.py',
  'handlers/context_menu.py',
  'handlers/process_actions.py',
]

install_data(process_manager_sources, install_dir: moduledir)
install_data(dialogs_sources, install_dir: moduledir / 'dialogs')
install_data(tabs_sources, install_dir: moduledir / 'tabs')
install_data(ui_sources, install_dir: moduledir / 'ui')
install_data(handlers_sources, install_dir: moduledir / 'handlers')

