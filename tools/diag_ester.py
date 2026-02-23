# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import os


def yn(x: bool) -> str:
    return 'YES' if x else 'NO'


def main() -> int:
    has_torch = False
    has_cuda = False
    gpu_count = 0
    torch_err = ''

    try:
        import torch  # type: ignore

        has_torch = True
        has_cuda = bool(getattr(torch, 'cuda', None) and torch.cuda.is_available())
        gpu_count = int(torch.cuda.device_count()) if has_cuda else 0
    except Exception as e:
        torch_err = str(e)

    internet_enabled = False
    web_provider = ''
    try:
        ia = importlib.import_module('bridges.internet_access')
        internet = getattr(ia, 'internet', None)
        internet_enabled = bool(getattr(internet, 'enabled', True)) if internet is not None else False
        web_provider = getattr(internet, 'provider', None) or 'ddgs'
    except Exception as e:
        web_provider = 'IMPORT_FAIL: ' + str(e)

    print('A: DIAG')
    print('  torch:', yn(has_torch), ('' if has_torch else f'({torch_err})'))
    print('  cuda :', yn(has_cuda))
    print('  gpu_count:', gpu_count)
    print('  internet_enabled:', yn(internet_enabled))
    print('  web_provider:', web_provider)

    print('ENV hints:')
    for k in ['CLOSED_BOX', 'DDGS_REGION', 'DDGS_TIMELIMIT', 'DDGS_SAFESEARCH']:
        print(f'  {k}={os.environ.get(k, "")}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
