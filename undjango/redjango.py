from . import undjango

"""
Functions to reverse the undjango process.
"""

def unalias(data, **options):
    for alias, accessor in options.get('aliases', []):
        data[accessor] = data[alias]
        del data[alias]
    return data

def redjango(data, **options):
    options = undjango._defaults(options)
    return unalias(data, **options)

