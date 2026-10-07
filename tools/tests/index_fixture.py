"""Bind synthetic test indexes to a manifest without touching production resources."""
import sqlite3
from sc2_catalog_inputs import index_inputs, inventory, save_manifest
from sc2_dependencies import RECURSION_DISABLED

def stamp(database, root, mods=(), dependencies=None, recursive=True):
    build_id = "fixture-build"
    db=sqlite3.connect(database)
    db.execute("CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT)")
    db.execute("INSERT OR REPLACE INTO metadata VALUES ('build_id',?)",(build_id,))
    db.commit();db.close()
    primary = mods[0] if mods else None
    state=dependencies or ({"status":"partial","problems":[RECURSION_DISABLED]} if not recursive else {"status":"complete","problems":[]})
    save_manifest(database, inventory(index_inputs(root,mods)),dependencies=state,build_id=build_id,
                  selection={"workspace_root":str(root),"primary":str(primary) if primary else None,
                             "mods_dir":str(primary.parent) if primary else None,"recursive":recursive,"explicit":True})
