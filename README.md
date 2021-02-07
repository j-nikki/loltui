# loltui

This is a proof-of-concept LoL assistant using a TUI-interface. When you join a lobby it tells the following.

* 5 most recent ranked game outcomes
* Champion points for hovered champion

## Installation

1. `git clone git@github.com:j-nikki/loltui.git`
2. `pip install loltui`

## Usage

1. Make a `loltui/devkey.py` that'll define your key as `DEV_KEY = 'RGAPI-...'`
2. `py -m loltui`