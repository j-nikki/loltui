import setuptools

with open('README.md') as f:
    readme = f.read()

with open('requirements.txt') as f:
    requirements = f.read()

setuptools.setup(
    name="loltui",
    version="0.1.0",
    author="j-nikki",
    author_email="72250615+j-nikki@users.noreply.github.com",
    description="LoL assistant with a TUI-interface",
    long_description=readme,
    long_description_content_type="text/markdown",
    keywords="lol league of legends champ champion select",
    url="https://github.com/j-nikki/loltui",
    packages=setuptools.find_packages('.', exclude='test'),
    python_requires='~=3.9',
    install_requires=requirements.splitlines(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows :: Windows 10",
        "Topic :: Games/Entertainment :: Real Time Strategy"
    ],
)
