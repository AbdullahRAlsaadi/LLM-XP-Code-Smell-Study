def read(self):
    """Read the config file, if it exists. Using defaults otherwise."""
    for config_file in self.config_file_paths():
        if os.path.exists(config_file):
            try:
                if is_py3:
                    self.parser.read(config_file, encoding='utf-8')
                else:
                    self.parser.read(config_file)
                logger.info("Read configuration file '{0}'".format(config_file))
            except UnicodeDecodeError as err:
                logger.error("Cannot decode configuration file '{0}': {1}".format(config_file, err))
                sys.exit(1)
            # Save the loaded configuration file path (issue #374)
            self._loaded_config_file = config_file
            break

    # Quicklook
    if not self.parser.has_section('quicklook'):
        self.parser.add_section('quicklook')
        self.parser.set('quicklook', 'cpu_careful', '50')
        self.parser.set('quicklook', 'cpu_warning', '70')
        self.parser.set('quicklook', 'cpu_critical', '90')
        self.parser.set('quicklook', 'mem_careful', '50')
        self.parser.set('quicklook', 'mem_warning', '70')
        self.parser.set('quicklook', 'mem_critical', '90')
        self.parser.set('quicklook', 'swap_careful', '50')
        self.parser.set('quicklook', 'swap_warning', '70')
        self.parser.set('quicklook', 'swap_critical', '90')

    # CPU
    if not self.parser.has_section('cpu'):
        self.parser.add_section('cpu')
        self.parser.set('cpu', 'user_careful', '50')
        self.parser.set('cpu', 'user_warning', '70')
        self.parser.set('cpu', 'user_critical', '90')
        self.parser.set('cpu', 'iowait_careful', '50')
        self.parser.set('cpu', 'iowait_warning', '70')
        self.parser.set('cpu', 'iowait_critical', '90')
        self.parser.set('cpu', 'system_careful', '50')
        self.parser.set('cpu', 'system_warning', '70')
        self.parser.set('cpu', 'system_critical', '90')
        self.parser.set('cpu', 'steal_careful', '50')
        self.parser.set('cpu', 'steal_warning', '70')
        self.parser.set('cpu', 'steal_critical', '90')

    # Per-CPU
    if not self.parser.has_section('percpu'):
        self.parser.add_section('percpu')
        self.parser.set('percpu', 'user_careful', '50')
        self.parser.set('percpu', 'user_warning', '70')
        self.parser.set('percpu', 'user_critical', '90')
        self.parser.set('percpu', 'iowait_careful', '50')
        self.parser.set('percpu', 'iowait_warning', '70')
        self.parser.set('percpu', 'iowait_critical', '90')
        self.parser.set('percpu', 'system_careful', '50')
        self.parser.set('percpu', 'system_warning', '70')
        self.parser.set('percpu', 'system_critical', '90')

    # Load
    if not self.parser.has_section('load'):
        self.parser.add_section('load')
        self.parser.set('load', 'careful', '0.7')
        self.parser.set('load', 'warning', '1.0')
        self.parser.set('load', 'critical', '5.0')

    # Mem
    if not self.parser.has_section('mem'):
        self.parser.add_section('mem')
        self.parser.set('mem', 'careful', '50')
        self.parser.set('mem', 'warning', '70')
        self.parser.set('mem', 'critical', '90')

    # Swap
    if not self.parser.has_section('memswap'):
        self.parser.add_section('memswap')
        self.parser.set('memswap', 'careful', '50')
        self.parser.set('memswap', 'warning', '70')
        self.parser.set('memswap', 'critical', '90')

    # FS
    if not self.parser.has_section('fs'):
        self.parser.add_section('fs')
        self.parser.set('fs', 'careful', '50')
        self.parser.set('fs', 'warning', '70')
        self.parser.set('fs', 'critical', '90')

    # Sensors
    if not self.parser.has_section('sensors'):
        self.parser.add_section('sensors')
        self.parser.set('sensors', 'temperature_core_careful', '60')
        self.parser.set('sensors', 'temperature_core_warning', '70')
        self.parser.set('sensors', 'temperature_core_critical', '80')
        self.parser.set('sensors', 'temperature_hdd_careful', '45')
        self.parser.set('sensors', 'temperature_hdd_warning', '52')
        self.parser.set('sensors', 'temperature_hdd_critical', '60')
        self.parser.set('sensors', 'battery_careful', '80')
        self.parser.set('sensors', 'battery_warning', '90')
        self.parser.set('sensors', 'battery_critical', '95')

    # Process list
    if not self.parser.has_section('processlist'):
        self.parser.add_section('processlist')
        self.parser.set('processlist', 'cpu_careful', '50')
        self.parser.set('processlist', 'cpu_warning', '70')
        self.parser.set('processlist', 'cpu_critical', '90')
        self.parser.set('processlist', 'mem_careful', '50')
        self.parser.set('processlist', 'mem_warning', '70')
        self.parser.set('processlist', 'mem_critical', '90')
