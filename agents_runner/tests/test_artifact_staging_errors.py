import errno

from agents_runner.artifacts import _is_transient_staging_error


def test_staging_error_classification() -> None:
    assert _is_transient_staging_error(OSError(errno.ENOENT, "missing"))
    assert _is_transient_staging_error(OSError(errno.ENOTDIR, "not a directory"))
    assert not _is_transient_staging_error(OSError(errno.EACCES, "denied"))
    assert not _is_transient_staging_error(OSError("no errno"))
