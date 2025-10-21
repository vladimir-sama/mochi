import os
import sys
import shutil
import requests
import hashlib
import configparser
import json
from typing import Optional, Dict, Any, List
from rich.progress import (
    Progress,
    BarColumn,
    DownloadColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich import print

# --- Initialization ---
version : str = '2025.10.21'
file_directory: str = os.path.dirname(os.path.realpath(__file__))
executable_directory: str = file_directory

if getattr(sys, 'frozen', False):
    executable_directory = os.path.dirname(sys.executable)

config: configparser.ConfigParser = configparser.ConfigParser()
config.read(os.path.join(executable_directory, 'mochi.ini'))
server_url: str = config.get('mochi', 'server', fallback='http://127.0.0.1:8080')
token: Optional[str] = config.get('mochi', 'token', fallback=None)
headers: dict = {'Authorization': f'Bearer {token}'} if token else {}

# --- Utility Functions ---
def compute_sha1_hash(file_path: str) -> str:
    '''Compute the SHA1 hash of a file.'''
    hash_obj = hashlib.sha1()
    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def download_file(url: str, file_path: str, sha1_expected: Optional[str] = None) -> bool:
    '''Download a file with a kawaii pastel-style rich progress bar.'''
    response = requests.get(url, stream=True, headers=headers)

    if response.status_code != 200:
        print(f'[magenta]Download failed: HTTP {response.status_code}[/magenta]')
        return False

    total_size: int = int(response.headers.get('content-length', 0))
    with Progress(
        TextColumn('[cyan]🌸 Downloading…[/cyan]'),
        BarColumn(bar_width=None, complete_style='bright_blue', finished_style='violet', pulse_style='pink'),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task_id = progress.add_task(f'{os.path.basename(file_path)}', total=total_size)
        with open(file_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
                    progress.update(task_id, advance=len(chunk))

    if sha1_expected:
        local_hash: str = compute_sha1_hash(file_path)
        if local_hash != sha1_expected:
            print(f'[magenta]💔 SHA1 mismatch!\nExpected: {sha1_expected}\nGot:      {local_hash}[/magenta]')
            os.remove(file_path)
            return False

    return True

# --- Command Implementations ---
def command_touch() -> None:
    '''Ping the server to check if it is online.'''
    try:
        response = requests.get(f'{server_url}/api/touch')
        if response.status_code == 200:
            print('[bright_blue]✨ Server online! ✨[/bright_blue]')
        else:
            print(f'[violet]Server replied with code {response.status_code}[/violet]')
    except Exception as error:
        print(f'[pink]Error:[/] {error}[/pink]')


def command_list() -> None:
    '''Retrieve and display a list of available packages.'''
    try:
        response = requests.get(f'{server_url}/api/list')
        if response.status_code == 200:
            packages: List[str] = response.json()
            if not packages:
                print('[pink]No packages found.[/pink]')
                return
            print('[magenta]💖 Available Packages:[/magenta]')
            for package_name in packages:
                print(' 🌸', package_name)
        else:
            print(f'[violet]Server error: {response.status_code}[/violet]')
    except Exception as error:
        print(f'[pink]Error:[/] {error}[/pink]')


def command_fetch(package_name: str) -> None:
    '''Fetch a package.'''
    endpoint: str = f'{server_url}/api/get/{package_name}'
    response = requests.get(endpoint)

    if response.status_code != 200:
        print(f'[violet]💔 Package not found or server error ({response.status_code})[/violet]')
        return

    manifest: Dict[str, Any] = response.json()
    file_name: str = manifest['filename']
    sha1_hash: Optional[str] = manifest.get('sha1')
    download_url: str = f'{server_url}/api/download/{package_name}'

    file_path: str = os.path.join(os.getcwd(), file_name)

    print(f'[cyan]🌸 Fetching {package_name}…[/cyan]')

    if download_file(download_url, file_path, sha1_hash):
        print(f'[bright_blue]Done! → {file_path}[/bright_blue]')


# --- CLI Entry Point ---
def main() -> None:
    '''Main CLI command parser.'''
    if len(sys.argv) == 1:
        print('[magenta]🎀 Mochi CLI 🎀[/magenta]')
        print('[cyan]Usage:[/cyan]')
        print('  mochi touch                 # Ping server')
        print('  mochi list                  # List packages')
        print('  mochi fetch PACKAGE         # Fetch package')
        return

    command: str = sys.argv[1]

    if command == 'touch':
        command_touch()
    elif command == 'list':
        command_list()
    elif command == 'fetch':
        if len(sys.argv) < 3:
            print('[pink]Missing package name[/pink]')
            return
        package: str = sys.argv[2]
        command_fetch(package)
    else:
        print(f'[violet]Unknown command:[/] {command}[/violet]')


if __name__ == '__main__':
    main()
