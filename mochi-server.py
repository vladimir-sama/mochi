import os
import sys
import hashlib
import secrets
import configparser
from flask import Flask, jsonify, send_file, abort
from typing import Any, Dict, List

# --- Initialization ---

version : str = '2025.10.21'

app: Flask = Flask(__name__)
app.secret_key = secrets.token_hex(16)

file_directory: str = os.path.dirname(os.path.realpath(__file__))
executable_directory: str = file_directory

if getattr(sys, 'frozen', False):
    executable_directory = os.path.dirname(sys.executable)

package_directory: str = os.path.join(executable_directory, 'instance')
os.makedirs(package_directory, exist_ok=True)

# --- Configuration Handling ---

def load_configuration(file_path: str = 'server.ini') -> configparser.ConfigParser:
    '''Always load the configuration from disk. Creates a default one if missing.'''
    configuration: configparser.ConfigParser = configparser.ConfigParser()

    if not os.path.isfile(file_path):
        configuration['server'] = {'port': '8080'}
        with open(file_path, 'w') as config_file:
            configuration.write(config_file)
    else:
        configuration.read(file_path)

    return configuration


# --- Utility Functions ---

def compute_sha1_hash(file_path: str) -> str:
    '''Compute and return the SHA1 hash of a file.'''
    sha1_hash = hashlib.sha1()
    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            sha1_hash.update(chunk)
    return sha1_hash.hexdigest()


# --- API Endpoints ---

@app.route('/api/touch')
def api_touch() -> Any:
    '''Check if the server is online.'''
    return jsonify({'ok': True})


@app.route('/api/list')
def api_list_packages() -> Any:
    '''List all package names defined in the server configuration (excluding [server]).'''
    configuration: configparser.ConfigParser = load_configuration()
    package_names: List[str] = [section for section in configuration.sections() if section.lower() != 'server']
    return jsonify(package_names)


@app.route('/api/get/<package_name>')
def api_get_manifest(package_name: str) -> Any:
    '''Return manifest information for a given package (filename and SHA1 hash).'''
    configuration: configparser.ConfigParser = load_configuration()

    if package_name not in configuration:
        return abort(404, f'Package "{package_name}" not found in configuration file.')

    file_name: str = configuration.get(package_name, 'file', fallback=None)
    if not file_name:
        return abort(500, f'Missing "file" entry for [{package_name}] in configuration.')

    file_path: str = os.path.join(package_directory, file_name)
    if not os.path.isfile(file_path):
        return abort(404, f'File not found: {file_name}')

    sha1_hash: str = compute_sha1_hash(file_path)

    manifest: Dict[str, str] = {
        'name': package_name,
        'filename': file_name,
        'sha1': sha1_hash
    }

    return jsonify(manifest)


@app.route('/api/download/<package_name>')
def api_download_package(package_name: str) -> Any:
    '''Download a package file by name.'''
    configuration: configparser.ConfigParser = load_configuration()

    if package_name not in configuration:
        return abort(404, f'Package "{package_name}" not found in configuration file.')

    file_name: str = configuration.get(package_name, 'file', fallback=None)
    if not file_name:
        return abort(500, f'Missing "file" entry for [{package_name}] in configuration.')

    file_path: str = os.path.join(package_directory, file_name)
    if not os.path.isfile(file_path):
        return abort(404, f'File not found: {file_name}')

    return send_file(file_path, as_attachment=True)


# --- Entry Point ---

if __name__ == '__main__':
    configuration: configparser.ConfigParser = load_configuration()
    port: int = configuration.getint('server', 'port', fallback=8080)
    print(f'Koha Server running on port {port}')
    app.run(host='0.0.0.0', port=port)
