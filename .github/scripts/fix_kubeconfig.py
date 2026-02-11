#!/usr/bin/env python3
import os
import yaml

config_path = os.path.expanduser('~/.kube/config')
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

for user in config.get('users', []):
    if 'exec' in user.get('user', {}):
        user['user']['exec']['apiVersion'] = 'client.authentication.k8s.io/v1beta1'

with open(config_path, 'w') as f:
    yaml.dump(config, f)
