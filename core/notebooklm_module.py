"""Legacy shim. Real implementation moved to core/content_gen/backends/nblm.py."""
from core.content_gen.backends.nblm import (  # noqa: F401
    generate_and_notify,
    get_or_create_notebook,
    cmd_notebooks,
    _start_generation,
    _wait_for_artifact,
    _run,
    notebook_url,
    FORMAT_NAMES,
    NBLM_FORMATS,
    _NBLM_CMD_ARGS,
    NOTEBOOKLM_BIN,
    load_nb_state,
)
