import os
import sys
import subprocess
import shutil
import hashlib
import secrets
import configparser
from flask import Flask, jsonify, send_file, abort, request
from typing import Any, Optional

# --- Initialization ---

version : str = '2025.10.25'

app: Flask = Flask(__name__)
app.secret_key = secrets.token_hex(16)

file_directory: str = os.path.dirname(os.path.realpath(__file__))
executable_directory: str = file_directory

if getattr(sys, 'frozen', False):
    executable_directory = os.path.dirname(sys.executable)

package_directory: str = os.path.join(executable_directory, 'instance')
os.makedirs(package_directory, exist_ok=True)
runtime_directory: str = os.path.join(package_directory, 'runtime')
os.makedirs(runtime_directory, exist_ok=True)

CERT_FILE: str = os.path.join(runtime_directory, 'cert.pem')
KEY_FILE: str = os.path.join(runtime_directory, 'key.pem')

# --- Configuration Handling ---

def load_configuration(file_path: str = os.path.join(runtime_directory, 'server.ini')) -> configparser.ConfigParser:
    '''Always load the configuration from disk. Creates a default one if missing.'''
    configuration: configparser.ConfigParser = configparser.ConfigParser()

    if not os.path.isfile(file_path):
        configuration['server'] = {
            'port': '8080',
            'token': '0000'
        }
        with open(file_path, 'w') as config_file:
            configuration.write(config_file)
    else:
        configuration.read(file_path)

    return configuration


# --- Utility Functions ---

def generate_self_signed_cert(cert_file: str = CERT_FILE, key_file: str = KEY_FILE) -> None:
    '''Generate a self-signed certificate if it does not exist.'''
    if os.path.isfile(cert_file) and os.path.isfile(key_file):
        return

    print('Generating self-signed certificate...')
    subprocess.run([
        'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
        '-keyout', key_file,
        '-out', cert_file,
        '-days', '365',
        '-nodes',
        '-subj', '/CN=localhost'
    ], check=True)
    print('Self-signed certificate generated.')


def verify_token(config : configparser.ConfigParser) -> Any:
    valid_token : Optional[str] = config.get('mochi', 'token', fallback=None)
    provided_token : str = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
    if valid_token and provided_token != valid_token:
        abort(401, 'Invalid or missing token')


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


@app.route('/api/version')
def api_version() -> Any:
    '''Return the server version.'''
    return jsonify({'version': version})


@app.route('/api/list')
def api_list_packages() -> Any:
    '''List all package names defined in the server configuration (excluding [server]).'''
    configuration: configparser.ConfigParser = load_configuration()
    verify_token(configuration)
    package_names: list[str] = [section for section in configuration.sections() if section.lower() != 'server']
    return jsonify(package_names)


@app.route('/api/get/<package_name>')
def api_get_manifest(package_name: str) -> Any:
    '''Return manifest information for a given package (filename and SHA1 hash).'''
    configuration: configparser.ConfigParser = load_configuration()
    verify_token(configuration)

    if package_name not in configuration:
        return abort(404, f'Package "{package_name}" not found in configuration file.')

    file_name: str = configuration.get(package_name, 'file', fallback=None)
    if not file_name:
        return abort(500, f'Missing "file" entry for [{package_name}] in configuration.')

    file_path: str = os.path.join(package_directory, file_name)
    if not os.path.isfile(file_path):
        return abort(404, f'File not found: {file_name}')

    sha1_hash: str = compute_sha1_hash(file_path)

    manifest: dict[str, str] = {
        'name': package_name,
        'filename': file_name,
        'sha1': sha1_hash
    }

    return jsonify(manifest)


@app.route('/api/download/<package_name>')
def api_download_package(package_name: str) -> Any:
    '''Download a package file by name.'''
    configuration: configparser.ConfigParser = load_configuration()
    verify_token(configuration)

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
    generate_self_signed_cert()
    port: int = configuration.getint('server', 'port', fallback=8080)
    print(f'Mochi Server running on port {port}')
    app.run(host='0.0.0.0', port=port, ssl_context=(CERT_FILE, KEY_FILE))
