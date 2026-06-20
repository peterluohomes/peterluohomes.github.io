// ============================================================================
//  firebase-sync.js  —  shared cloud-sync module for the Pinnacle tools
//  Load in each tool as:  <script type="module" src="/firebase-sync.js"></script>
//  Each tool sets window.__SYNC = {...} BEFORE this file loads.
//  getData()/apply() may be sync OR async (return a Promise) — both work.
// ============================================================================

import { initializeApp } from "https://www.gstatic.com/firebasejs/12.15.0/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signInWithRedirect,
         getRedirectResult, signOut, onAuthStateChanged, browserLocalPersistence,
         setPersistence }
  from "https://www.gstatic.com/firebasejs/12.15.0/firebase-auth.js";
import { initializeFirestore, persistentLocalCache, persistentMultipleTabManager,
         doc, getDoc, setDoc, onSnapshot }
  from "https://www.gstatic.com/firebasejs/12.15.0/firebase-firestore.js";

// ============================================================================
//  >>> PASTE YOUR FIREBASE CONFIG VALUES HERE (replace each PASTE_... string) <<<
//  From: Firebase console > Project settings > General > Your apps.
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

const cfg = window.__SYNC || null;
let uid = null, unsub = null, lastAppliedAt = 0, lastPushedAt = 0;
let signinInProgress = false;
let applyingRemote = false;   // true while we apply cloud data, so it can't echo back as a save
// A stable id for THIS device/tab session, written with every save so we can
// recognise and ignore our own writes coming back through the listener.
const CLIENT_ID = (self.crypto && crypto.randomUUID) ? crypto.randomUUID()
  : (Date.now() + '-' + Math.random().toString(36).slice(2));

function $(id){ return document.getElementById(id); }
function setStatus(t){ const e = $('sync-status'); if (e) e.textContent = t; }
function tsOf(d){ return (d && d.savedAt) ? (Date.parse(d.savedAt) || 0) : 0; }
function docRef(){ return doc(db, 'users', uid, 'tools', cfg.toolName); }
function isMobile(){ return /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)
  || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1); } // iPadOS reports as Mac

async function readCloud(){
  try { const s = await getDoc(docRef()); return s.exists() ? s.data().payload : null; }
  catch(e){ console.warn('[sync] read failed', e); return null; }
}
async function writeCloud(data){
  try {
    await setDoc(docRef(), {
      payload: data,
      savedAt: (data && data.savedAt) || new Date().toISOString(),
      writer:  CLIENT_ID
    });
  }
  catch(e){ console.warn('[sync] write failed', e); }
}

// Apply remote data WITHOUT letting it trigger a save-back (echo).
async function applyRemote(data){
  applyingRemote = true;
  try { await cfg.apply(data); }
  catch(e){ console.warn('[sync] apply failed', e); }
  finally { applyingRemote = false; }
}
// Timestamp of whatever the tool currently has in memory RIGHT NOW.
async function localTs(){
  try { return tsOf(cfg.getData ? await cfg.getData() : null); }
  catch(e){ return 0; }
}

async function reconcile(){
  const local = cfg.getData ? await cfg.getData() : null;   // getData may be async
  const cloud = await readCloud();
  const lt = tsOf(local), ct = tsOf(cloud);
  if (cloud && ct > lt){
    lastAppliedAt = ct;
    await applyRemote(cloud);
  } else if (local && lt > ct){
    lastPushedAt = lt;
    await writeCloud(local);
  } else {
    // equal timestamps (or both empty) -> treat as already in sync, touch nothing
    lastAppliedAt = Math.max(lastAppliedAt, ct);
  }
  setStatus('Synced \u2713');
  if (unsub) unsub();
  unsub = onSnapshot(docRef(), async (snap) => {
    if (!snap.exists()) return;
    // Skip our own optimistic local write before the server confirms it.
    if (snap.metadata && snap.metadata.hasPendingWrites) return;
    const raw  = snap.data();
    const data = raw.payload, at = tsOf(data);
    // Skip our OWN write echoing back from the server.
    if (raw.writer === CLIENT_ID){ lastPushedAt = at; return; }
    // CRITICAL GUARD: only accept data that is strictly newer than what THIS
    // device currently holds. An idle device pushing a stale copy will have an
    // older (or equal) timestamp, so it can never roll back active work here.
    const here = await localTs();
    if (at <= here)          return;   // not newer than my live data -> ignore
    if (at <= lastAppliedAt) return;   // already applied something this fresh
    lastAppliedAt = at;
    await applyRemote(data);
    setStatus('Updated from another device \u2713');
  }, (err) => console.warn('[sync] snapshot error', err));
}

const Sync = {
  signIn: async function(){
    if (signinInProgress) return;            // block double-taps -> no cancelled-popup-request
    signinInProgress = true;
    setStatus('Opening sign-in...');
    const provider = new GoogleAuthProvider();
    try {
      if (false){
        await signInWithRedirect(auth, provider);   // page navigates away & back; reliable on iOS
        return;                                      // signinInProgress reset on reload
      }
      await signInWithPopup(auth, provider);
    } catch(e){
      const code = e && e.code;
      if (code === 'auth/cancelled-popup-request' || code === 'auth/popup-closed-by-user'){
        // benign: user double-tapped or closed the window -- no alert
      } else if (code === 'auth/popup-blocked'){
        try { await signInWithRedirect(auth, provider); return; } catch(_){}
      } else {
        alert('Sign-in failed: ' + (e && e.message ? e.message : e));
        setStatus('Not signed in');
      }
    } finally {
      signinInProgress = false;
    }
  },
  signOut: function(){ signOut(auth); },
  notifyChanged: async function(){
    if (!uid || !cfg || !cfg.getData) return;
    if (applyingRemote) return;                 // don't save data we're mid-applying from the cloud
    const data = await cfg.getData();          // getData may be async
    if (!data) return;
    const at = tsOf(data);
    if (at && at <= lastAppliedAt) return;      // not newer than what we just applied -> spurious, skip
    lastPushedAt = at;
    await writeCloud(data);
    setStatus('Synced \u2713');
  }
};
window.PinnacleSync = Sync;

// Keep the session across reloads, and surface any redirect-flow errors.
setPersistence(auth, browserLocalPersistence).catch(function(e){ console.warn('[sync] persistence', e); });
getRedirectResult(auth).catch(function(e){ console.warn('[sync] redirect result', e); });

onAuthStateChanged(auth, (user) => {
  const btn = $('sync-signin');
  if (user){
    uid = user.uid;
    if (btn) btn.style.display = 'none';
    setStatus('Signed in -- syncing...');
    if (cfg) reconcile();
  } else {
    uid = null;
    if (unsub){ unsub(); unsub = null; }
    if (btn) btn.style.display = '';
    setStatus('Not signed in');
  }
});
