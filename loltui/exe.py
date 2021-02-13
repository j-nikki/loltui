import io
import os
import subprocess
import sys
import tempfile
import zipfile

import requests

with tempfile.TemporaryDirectory() as d_tmp:
    print('Downloading UPX 3.96')
    r = requests.get(
        'https://github.com/upx/upx/releases/download/v3.96/upx-3.96-win64.zip')
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extract('upx-3.96-win64/upx.exe', d_tmp)

    print('  Done\nEngaging venv')
    subprocess.check_call([sys.executable, '-m', 'venv', d_tmp], shell=True)

    subprocess.check_call([os.path.join(d_tmp,
                                        'Scripts',
                                        'pip'),
                           'install',
                           'pycparser==2.14',  # https://github.com/eliben/pycparser/issues/291
                           'PyInstaller',
                           'psutil',
                           'requests',
                           'keyboard'], shell=True)

    d_src = os.path.dirname(__file__)
    subprocess.check_call([os.path.join(d_tmp, 'Scripts', 'python'), '-OO', '-m', 'PyInstaller',
                           os.path.join(d_src, '__main__.py'),
                           '-F',
                           '--upx-dir',
                           os.path.join(d_tmp, 'upx-3.96-win64'),
                           '--workpath',
                           d_tmp,
                           '--specpath',
                           d_tmp,
                           '--distpath',
                           '.',
                           '-n',
                           'loltui',
                           '-p',
                           d_src,
                           '-i',
                           os.path.join(d_src, '..', 'images', 'icon.ico')], shell=True)


print(f'Generated EXE at: {os.path.abspath("loltui.exe")}')
exit(0)
