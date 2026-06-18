// ============================================================================
//  firebase-sync.js  —  shared cloud-sync module for the Pinnacle tools
//  Loaded by each tool as:  <script type="module" src="firebase-sync.js"></script>
//
//  Each tool, BEFORE loading this file, sets window.__SYNC = { ... } describing
//  how to read/apply its own data. This file handles sign-in, reconciliation,
//  and live cross-device updates. Config is entered ONCE, right below.
// ============================================================================

import { initializeApp } from "https://www.gstatic.com/firebasejs/12.15.0/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged }
  from "https://www.gstatic.com/firebasejs/12.15.0/firebase-auth.js";
import { initializeFirestore, persistentLocalCache, persistentMultipleTabManager,
         doc, getDoc, setDoc, onSnapshot }
  from "https://www.gstatic.com/firebasejs/12.15.0/firebase-firestore.js";

// ============================================================================
//  >>> PASTE YOUR FIREBASE CONFIG VALUES HERE (replace each PASTE_… string) <<<
//  Copy them from: Firebase console > Project settings > General > Your apps.
//  Copy storageBucket EXACTLY (newer projects end in .firebasestorage.app).
// ============================================================================
const firebaseConfig = {
  apiKey: "AIzaSyA0qVGs4LRXBa3AXAMVwv2rm0svO4neL0M",
  authDomain: "pltuls.firebaseapp.com",
  projectId: "pltuls",
  storageBucket: "pltuls.firebasestorage.app",
  messagingSenderId: "1051163830614",
  appId: "1:1051163830614:web:749bfca4e49245cc2bcef7"};
// ============================================================================

const app  = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db   = initializeFirestore(app, {
  localCache: persistentLocalCache({ tabManager: persistentMultipleTabManager() })
});

const cfg = window.__SYNC || null;   // set by each tool before this module loads
let uid          = null;
let unsub        = null;
let lastAppliedAt = 0;   // timestamp of the most recent data we wrote to the UI
let lastPushedAt  = 0;   // timestamp of the most recent data we pushed (echo guard)

function $(id){ return document.getElementById(id); }
function setStatus(t){ const e = $('sync-status'); if (e) e.textContent = t; }
function tsOf(d){ return (d && d.savedAt) ? (Date.parse(d.savedAt) || 0) : 0; }
function docRef(){ return doc(db, 'users', uid, 'tools', cfg.toolName); }

async function readCloud(){
  try { const s = await getDoc(docRef()); return s.exists() ? s.data().payload : null; }
  catch(e){ console.warn('[sync] cloud read failed', e); return null; }
}
async function writeCloud(data){
  try {
    await setDoc(docRef(), { payload: data, savedAt: (data && data.savedAt) || new Date().toISOString() });
  } catch(e){ console.warn('[sync] cloud write failed', e); }
}

// On sign-in: decide whether cloud or local is newer, seed/apply accordingly,
// then subscribe to live changes from other devices.
async function reconcile(){
  const local = cfg.getData ? cfg.getData() : null;
  const cloud = await readCloud();
  const lt = tsOf(local), ct = tsOf(cloud);

  if (cloud && ct >= lt){          // cloud is newer (or local empty) -> pull down
    lastAppliedAt = ct;
    try { cfg.apply(cloud); } catch(e){ console.warn('[sync] apply failed', e); }
  } else if (local){               // local is newer (or no cloud yet) -> push up
    lastPushedAt = lt;
    await writeCloud(local);
  }
  setStatus('Synced \u2713');

  if (unsub) unsub();
  unsub = onSnapshot(docRef(), (snap) => {
    if (!snap.exists()) return;
    const data = snap.data().payload;
    const at = tsOf(data);
    // Apply only genuinely newer data that isn't the echo of our own push.
    if (at > lastAppliedAt && at !== lastPushedAt){
      lastAppliedAt = at;
      try { cfg.apply(data); } catch(e){ console.warn('[sync] apply failed', e); }
      setStatus('Updated from another device \u2713');
    }
  }, (err) => console.warn('[sync] snapshot error', err));
}

const Sync = {
  signIn:  async function(){
    try { await signInWithPopup(auth, new GoogleAuthProvider()); }
    catch(e){ alert('Sign-in failed: ' + (e && e.message ? e.message : e)); }
  },
  signOut: function(){ signOut(auth); },
  // Tools call this right after a local save so the change propagates to the cloud.
  notifyChanged: async function(){
    if (!uid || !cfg || !cfg.getData) return;
    const data = cfg.getData();
    if (!data) return;
    lastPushedAt = tsOf(data);
    await writeCloud(data);
    setStatus('Synced \u2713');
  }
};
window.PinnacleSync = Sync;

onAuthStateChanged(auth, (user) => {
  const btn = $('sync-signin');
  if (user){
    uid = user.uid;
    if (btn) btn.style.display = 'none';
    setStatus('Signed in \u2014 syncing\u2026');
    if (cfg) reconcile();
  } else {
    uid = null;
    if (unsub){ unsub(); unsub = null; }
    if (btn) btn.style.display = '';
    setStatus('Not signed in');
  }
});
