# Conditional bed_mesh compatibility router.
#
# Creality K1 Max firmware 2.3.5.33 needs its stock bed_mesh implementation
# for the proprietary PRTouch/CFS path.  The BTT Eddy path needs the newer
# implementation shipped in this repository.  The installer preserves the
# stock module as bed_mesh_creality.py before this file is installed.


def load_config(config):
    if config.get_prefix_sections('probe_eddy_current '):
        from .upgrade import bed_mesh as implementation
    else:
        from . import bed_mesh_creality as implementation
    return implementation.load_config(config)
