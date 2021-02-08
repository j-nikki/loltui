import sys

if sys.argv[1:] == ('--exe'):
    import io
    import os
    import tempfile
    import zipfile
    import requests
    import subprocess

    with tempfile.TemporaryDirectory() as d_tmp:
        r = requests.get(
            'https://github.com/upx/upx/releases/download/v3.96/upx-3.96-win64.zip')
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extract('upx-3.96-win64/upx.exe', d_tmp)
        d_src = os.path.dirname(sys.argv[0])

        subprocess.call([sys.executable, '-m', 'venv', d_tmp])
        subprocess.call([os.path.join(d_tmp,
                                      'Scripts',
                                      'pip'),
                         'install',
                         'pycparser==2.14',  # https://github.com/eliben/pycparser/issues/291
                         'PyInstaller',
                         'psutil',
                         'requests'])
        subprocess.call([os.path.join(d_tmp, 'Scripts', 'python'), '-OO', '-m', 'PyInstaller',
                         os.path.join(d_src, 'loltui.py'),
                         '-F',
                         '--upx-dir',
                         os.path.join(d_tmp, 'upx-3.96-win64'),
                         '--workpath',
                         d_tmp,
                         '--specpath',
                         d_tmp,
                         '--distpath',
                         '.',
                         '--clean',
                         '-p',
                         d_src,
                         '-i',
                         os.path.join(d_src, 'images', 'icon.ico')])
else:
    import loltui.loltui
