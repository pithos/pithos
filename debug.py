#!/usr/bin/env python3

import os
import sys

# None of this works on Windows atm
if sys.platform != 'win32':

    # Store config locally
    config_dir = os.path.abspath('./config')
    os.environ['XDG_CONFIG_HOME'] = config_dir

    # Migrate old debug_config
    old_config_dir = os.path.abspath('./debug_config')
    if os.path.exists(old_config_dir):
        os.rename(old_config_dir, config_dir)

    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    # Enable verbose logging and test mode
    if len(sys.argv) == 1:
        sys.argv.append('-tvv')

from pithos import application

application.main()
