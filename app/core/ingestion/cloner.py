import shutil
import tempfile
from pathlib import Path

import structlog
from git import GitCommandError, Repo

log = structlog.get_logger()


async def clone_repo(repo_url: str, repo_id: str) -> Path:
    """
    Clone a remote Git repository to a temporary local directory.
    Returns the path to the cloned repo.
    Raises ValueError if the clone fails.

    We use depth=1 (shallow clone) — we only need the latest
    state of the files, not the full git history.
    Full history would take 10x longer and use 10x more disk.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"codesync_{repo_id}_"))

    log.info("clone_started", repo_id=repo_id, repo_url=repo_url)

    try:
        Repo.clone_from(
            repo_url,
            tmp_dir,
            depth=1,        # shallow clone — latest state only
            single_branch=True,  # only default branch
        )
        log.info("clone_complete", repo_id=repo_id, path=str(tmp_dir))
        return tmp_dir

    except GitCommandError as e:
        # Clean up temp dir if clone failed
        shutil.rmtree(tmp_dir, ignore_errors=True)
        log.error("clone_failed", repo_id=repo_id, error=str(e))
        
        clean_error = e.stderr.strip().replace('\n', ' ') if e.stderr else "Repository not found or access denied."
        raise ValueError(f"Failed to clone '{repo_url}': {clean_error}")


def cleanup_repo(path: Path) -> None:
    """
    Delete the temporary clone directory.
    On Windows, git marks some files as read-only.
    We need a custom error handler to force-delete them.
    """
    import stat

    def force_remove_readonly(func, fpath, _excinfo):
        # Remove read-only flag then retry deletion
        Path(fpath).chmod(stat.S_IWRITE)
        func(fpath)

    shutil.rmtree(path, onerror=force_remove_readonly)
    log.info("clone_cleanup", path=str(path))