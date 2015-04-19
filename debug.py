#!/usr/bin/env python3

import os
import sys

# None of this works on Windows atm
if sys.platform != 'win32':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config', help='Use a specific config directory. Default: ./config')
    args, leftover_args = parser.parse_known_args()
    sys.argv = sys.argv[0:1] + leftover_args

    # Store config locally
    config_dir = os.path.abspath(args.config)
    os.environ['XDG_CONFIG_HOME'] = config_dir

    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    # Enable verbose logging and test mode
    if len(sys.argv) == 1:
        sys.argv.append('-tv')

from pithos import pithos

pithos.main()
