// Hands a ROM from the landing page ("insert cartridge") to an editor page. The bytes go through IndexedDB on
// this site's own origin, so they never leave the browser; the editor takes them once and the entry is deleted.
(function (root) {
  const DB = "rom-studio-handoff", STORE = "rom", KEY = "pending", MAX_AGE = 5 * 60 * 1000;
  function open() {
    return new Promise((ok, fail) => {
      if (!root.indexedDB) return fail(new Error("This browser can't hand the ROM to the editor."));
      const req = root.indexedDB.open(DB, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE);
      req.onsuccess = () => ok(req.result); req.onerror = () => fail(req.error);
    });
  }
  function run(mode, fn) {
    return open().then(db => new Promise((ok, fail) => {
      const tx = db.transaction(STORE, mode), st = tx.objectStore(STORE), out = fn(st);
      tx.oncomplete = () => { db.close(); ok(out && out.result); }; tx.onerror = () => { db.close(); fail(tx.error); };
    }));
  }
  // put(name, Uint8Array): store the ROM for the next editor that opens
  function put(name, bytes) { return run("readwrite", st => st.put({ name, bytes, at: Date.now() }, KEY)); }
  // take(): the stored ROM as a File (or null), removed so a reload doesn't open it again
  async function take() {
    let got = null;
    try {
      await run("readwrite", st => { const r = st.get(KEY); r.onsuccess = () => { got = r.result || null; if (got) st.delete(KEY); }; return null; });
    } catch (e) { return null; }
    if (!got || Date.now() - got.at > MAX_AGE) return null;
    return new File([got.bytes], got.name);
  }
  root.RomHandoff = { put, take };
})(typeof window !== "undefined" ? window : globalThis);
