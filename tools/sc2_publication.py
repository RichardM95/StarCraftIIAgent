"""Same-parent directory publication with one tool-owned previous version."""
import json
import shutil
import uuid
import warnings
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path


class PublicationRecoveryError(RuntimeError):
    """Recovery was interrupted; all surviving paths must be preserved for inspection."""


@contextmanager
def staged_directory(target):
    target = Path(target).resolve()
    stage = Path(tempfile.mkdtemp(prefix="." + target.name + ".stage-", dir=target.parent))
    preserve = False
    try:
        yield stage
    except PublicationRecoveryError:
        preserve = True
        raise
    finally:
        if not preserve and stage.exists():
            confined(stage, target.parent)
            shutil.rmtree(stage)


def confined(path, parent):
    lexical = Path(path)
    if lexical.is_symlink():
        raise ValueError("Publication path must not be a link: " + str(lexical))
    try:
        attributes = getattr(lexical.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        attributes = 0
    if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        raise ValueError("Publication path must not be a junction/reparse point: " + str(lexical))
    path = lexical.resolve()
    parent = Path(parent).resolve()
    if path.parent != parent:
        raise ValueError("Publication path must be a direct child of " + str(parent))
    return path


def publish_directory(stage, target, kind):
    stage, target = Path(stage).resolve(), Path(target).resolve()
    parent = target.parent
    confined(stage, parent); confined(target, parent)
    backup = confined(parent / ("." + target.name + ".sc2-previous"), parent)
    owner = confined(parent / ("." + target.name + ".sc2-previous.owner.json"), parent)
    expected = {"tool": "SC2ModAgent", "kind": kind, "target": str(target)}
    if backup.exists():
        try:
            valid = json.loads(owner.read_text()) == expected
        except (OSError, ValueError):
            valid = False
        if not valid or backup.is_symlink():
            raise ValueError("Refusing to rotate an unowned previous directory: " + str(backup))
    elif owner.exists():
        raise ValueError("Previous-version ownership marker exists without its directory: " + str(owner))
    lock = confined(parent / ("." + target.name + ".sc2-publish.lock"), parent)
    lock.mkdir()  # exclusive ownership; an existing lock requires investigation
    retired = confined(parent / ("." + target.name + ".sc2-retired-" + uuid.uuid4().hex), parent)
    old_owner = None
    owner_loaded = False
    moved_old = installed = rotated = False
    try:
        old_owner = owner.read_bytes() if owner.exists() else None
        owner_loaded = True
        if backup.exists():
            backup.rename(retired); rotated = True
        if target.exists():
            target.rename(backup); moved_old = True
        stage.rename(target); installed = True
        if moved_old:
            owner.write_text(json.dumps(expected), encoding="utf-8")
        elif rotated:
            # No current target means the older backup is still the previous version.
            retired.rename(backup); rotated = False
        if rotated:
            confined(retired, parent)
            try:
                shutil.rmtree(retired)
            except OSError as exc:
                warnings.warn("Publication succeeded; retired tool backup cleanup pending: " + str(retired) + ": " + str(exc))
    except Exception as original:
        try:
            if installed:
                target.rename(stage)
            if moved_old:
                backup.rename(target)
            if rotated and retired.exists():
                retired.rename(backup)
            if owner_loaded:
                if old_owner is None:
                    owner.unlink(missing_ok=True)
                else:
                    owner.write_bytes(old_owner)
        except Exception as recovery:
            locations = "\n".join(f"{name}: {path} (exists={path.exists()})"
                         for name, path in (("stage", stage), ("target", target), ("previous", backup),
                                            ("retired", retired), ("ownership", owner)))
            raise PublicationRecoveryError("Publication failed and recovery was incomplete; preserve these paths:\n"
                                           + locations + "\noriginal=" + repr(original)
                                           + "; recovery=" + repr(recovery)) from original
        raise
    finally:
        try:
            lock.rmdir()
        except OSError as error:
            warnings.warn("Publication lock cleanup pending (does not replace the primary result): " + str(lock) + ": " + str(error))

    return target
