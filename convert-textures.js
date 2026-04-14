#!/usr/bin/env node
'use strict';
/**
 * convert-textures.js
 * Converts all PNG textures in assets/textures/ into embedded JS hex data.
 * Patches index.html to use BABYLON.RawTexture + canvas-decoded Image objects.
 * Deletes the textures directory after patching.
 */

const fs   = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// ── Ensure pngjs is available ─────────────────────────────────────────────────
let PNG;
try {
  PNG = require('pngjs').PNG;
} catch (e) {
  console.log('Installing pngjs...');
  execSync('npm install --save-dev pngjs', { cwd: __dirname, stdio: 'inherit' });
  PNG = require('pngjs').PNG;
}

const TEXTURES_DIR = path.join(__dirname, 'assets', 'textures');
const INDEX_HTML   = path.join(__dirname, 'index.html');

// ── Read PNG → { w, h, d: hexString } ────────────────────────────────────────
function readPNG(file) {
  const buf = fs.readFileSync(file);
  const png = PNG.sync.read(buf);
  return { w: png.width, h: png.height, d: Buffer.from(png.data).toString('hex') };
}

// ── Collect textures ──────────────────────────────────────────────────────────
const textures = {};

if (!fs.existsSync(TEXTURES_DIR)) {
  console.error('Textures directory not found:', TEXTURES_DIR);
  process.exit(1);
}

// Main textures
for (const f of fs.readdirSync(TEXTURES_DIR)) {
  if (!f.endsWith('.png')) continue;
  const name = f.replace('.png', '');
  console.log('Reading:', name);
  textures[name] = readPNG(path.join(TEXTURES_DIR, f));
}

// Preview textures
const previewDir = path.join(TEXTURES_DIR, 'previews');
if (fs.existsSync(previewDir)) {
  for (const f of fs.readdirSync(previewDir)) {
    if (!f.endsWith('.png')) continue;
    const name = 'previews/' + f.replace('.png', '');
    console.log('Reading:', name);
    textures[name] = readPNG(path.join(previewDir, f));
  }
}

console.log(`\nLoaded ${Object.keys(textures).length} textures`);

// ── Generate injected <script> content ───────────────────────────────────────
// Texture data object (hex-encoded RGBA pixel data)
let texDataJS = 'var __TEX__={\n';
for (const [name, t] of Object.entries(textures)) {
  texDataJS += `"${name}":{w:${t.w},h:${t.h},d:"${t.d}"},\n`;
}
texDataJS += '};\n';

// Runtime helpers:
//   __TEXURI__[name]       = data URI (for Image.src assignments)
//   __mkTex__(n,sc,nm,iy,sp) = BABYLON.RawTexture (for 3D meshes)
const helperJS = `var __TEXURI__={};
!function(){
  function h2u(s){
    var d=new Uint8Array(s.length>>1);
    for(var i=0;i<d.length;i++){
      var b=s.charCodeAt(i<<1),c=s.charCodeAt((i<<1)+1);
      d[i]=((b<58?b-48:b-87)<<4)|(c<58?c-48:c-87);
    }
    return d;
  }
  Object.keys(__TEX__).forEach(function(k){
    var t=__TEX__[k];
    var raw=h2u(t.d);
    t.b=raw;
    var cv=document.createElement('canvas');
    cv.width=t.w; cv.height=t.h;
    cv.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(raw.buffer),t.w,t.h),0,0);
    __TEXURI__[k]=cv.toDataURL();
  });
}();
function __mkTex__(n,sc,nm,iy,sp){
  var uri=__TEXURI__[n];
  if(!uri){console.error('TEX missing:',n);return null;}
  if(sp==null)sp=BABYLON.Texture.NEAREST_SAMPLINGMODE;
  return new BABYLON.Texture(uri,sc,nm,iy,sp);
}
function __mkTerrainTex__(path,sc,sp){
  var n=path.replace('assets/textures/','').replace('.png','');
  var uri=__TEXURI__[n];
  if(!uri){console.error('Terrain TEX missing:',n);return null;}
  return new BABYLON.Texture(uri,sc,true,false,sp||BABYLON.Texture.NEAREST_SAMPLINGMODE);
}`;

const injectedScript = `<script>\n${texDataJS}${helperJS}\n</script>\n`;

// ── Patch index.html ──────────────────────────────────────────────────────────
console.log('\nPatching index.html...');
let html = fs.readFileSync(INDEX_HTML, 'utf8');
const originalLen = html.length;

function requireReplaced(html, old, neu, label) {
  const count = (html.split(old).length - 1);
  if (count === 0) throw new Error(`Pattern not found: ${label || old.slice(0,60)}`);
  return html.split(old).join(neu);
}

function requireReplacedN(html, old, neu, expectedCount, label) {
  const count = (html.split(old).length - 1);
  if (count !== expectedCount)
    throw new Error(`Expected ${expectedCount} occurrences of "${label || old.slice(0,60)}", found ${count}`);
  return html.split(old).join(neu);
}

// 1. Inject before the webpack bundle script tag
const WEBPACK_MARKER_CRLF = '<script>\r\n!(function (e) {';
const WEBPACK_MARKER_LF   = '<script>\n!(function (e) {';
let wpIdx = html.indexOf(WEBPACK_MARKER_CRLF);
let wpMarker = WEBPACK_MARKER_CRLF;
if (wpIdx === -1) {
  wpIdx = html.indexOf(WEBPACK_MARKER_LF);
  wpMarker = WEBPACK_MARKER_LF;
}
if (wpIdx === -1) throw new Error('Cannot find webpack bundle start');
html = html.slice(0, wpIdx) + injectedScript + html.slice(wpIdx);
console.log('✓ Injected texture script');

// 2. CSS backgrounds (background.jpg → dark gradient)
html = requireReplacedN(html,
  'url("assets/textures/background.jpg")',
  'linear-gradient(135deg,#3d3028 0%,#1e1814 100%)',
  2, 'CSS background.jpg'
);
console.log('✓ CSS backgrounds');

// 3. Registry block texture loader (noa engine registry.js, line ~102614)
html = requireReplaced(html,
  'new BABYLON.Texture(this._texturePath + i, this.noa.rendering._scene, !1, !0, BABYLON.Constants.TEXTURE_NEAREST_NEAREST_MIPNEAREST)',
  '__mkTex__(i.replace(/\\.png$/,""),this.noa.rendering._scene,!1,!0,BABYLON.Constants.TEXTURE_NEAREST_NEAREST_MIPNEAREST)',
  'registry BABYLON.Texture'
);
console.log('✓ Registry texture loader');

// 4. Plant/foliage block mesh textures (bush, flowers, mushrooms — J = Y[3..7])
html = requireReplaced(html,
  'new BABYLON.Texture("assets/textures/" + J + ".png", scene, !0, !0, 1)',
  '__mkTex__(J,scene,!0,!0,1)',
  'foliage BABYLON.Texture'
);
console.log('✓ Foliage block textures');

// 5. Steve model textures
html = requireReplaced(html,
  'new BABYLON.Texture("assets/textures/stevehead.png", t, !0, !1, BABYLON.Texture.NEAREST_SAMPLINGMODE)',
  '__mkTex__("stevehead",t,!0,!1,BABYLON.Texture.NEAREST_SAMPLINGMODE)',
  'stevehead'
);
html = requireReplaced(html,
  'new BABYLON.Texture("assets/textures/stevetorso.png", t, !0, !1, BABYLON.Texture.NEAREST_SAMPLINGMODE)',
  '__mkTex__("stevetorso",t,!0,!1,BABYLON.Texture.NEAREST_SAMPLINGMODE)',
  'stevetorso'
);
html = requireReplaced(html,
  'new BABYLON.Texture("assets/textures/stevearm.png", t, !0, !1, BABYLON.Texture.NEAREST_SAMPLINGMODE)',
  '__mkTex__("stevearm",t,!0,!1,BABYLON.Texture.NEAREST_SAMPLINGMODE)',
  'stevearm'
);
html = requireReplaced(html,
  'new BABYLON.Texture("assets/textures/steveleg.png", t, !0, !1, BABYLON.Texture.NEAREST_SAMPLINGMODE)',
  '__mkTex__("steveleg",t,!0,!1,BABYLON.Texture.NEAREST_SAMPLINGMODE)',
  'steveleg'
);
console.log('✓ Steve model textures');

// 6. Particle debris textures
html = requireReplaced(html,
  'new BABYLON.Texture("assets/textures/grass_dirt.png", t, !0, !1, BABYLON.Constants.TEXTURE_NEAREST_NEAREST_MIPNEAREST)',
  '__mkTex__("grass_dirt",t,!0,!1,BABYLON.Constants.TEXTURE_NEAREST_NEAREST_MIPNEAREST)',
  'grass_dirt particle'
);
// grass.png is constructed but result immediately discarded via comma operator
html = requireReplaced(html,
  'new BABYLON.Texture("assets/textures/grass.png", t, !0, !1)',
  'null',
  'grass particle (discarded)'
);
console.log('✓ Particle debris textures');

// 7. Clouds
html = requireReplaced(html,
  'new BABYLON.Texture("assets/textures/clouds.png", t, !0, !0, BABYLON.Texture.NEAREST_SAMPLINGMODE)',
  '__mkTex__("clouds",t,!0,!0,BABYLON.Texture.NEAREST_SAMPLINGMODE)',
  'clouds'
);
console.log('✓ Clouds texture');

// 8. Crosshair (no noMip/invertY/sampling args → use defaults matching BABYLON.Texture)
html = requireReplaced(html,
  'new BABYLON.Texture("assets/textures/crosshair.png", scene)',
  '__mkTex__("crosshair",scene,false,true,BABYLON.Texture.NEAREST_SAMPLINGMODE)',
  'crosshair'
);
console.log('✓ Crosshair texture');

// 9. Bedrock (appears twice — two side planes)
html = requireReplacedN(html,
  'new BABYLON.Texture("assets/textures/bedrock.png", scene, !0, !0, BABYLON.Texture.NEAREST_SAMPLINGMODE)',
  '__mkTex__("bedrock",scene,!0,!0,BABYLON.Texture.NEAREST_SAMPLINGMODE)',
  2, 'bedrock'
);
console.log('✓ Bedrock textures (×2)');

// 10. Image.src static texture URLs (used by 2D canvas UI)
const staticImgMap = {
  '"assets/textures/dirt.png"':             '__TEXURI__["dirt"]',
  '"assets/textures/button.png"':           '__TEXURI__["button"]',
  '"assets/textures/button_over.png"':      '__TEXURI__["button_over"]',
  '"assets/textures/hotbar_bg.png"':        '__TEXURI__["hotbar_bg"]',
  '"assets/textures/hotbar_selection.png"': '__TEXURI__["hotbar_selection"]',
};
for (const [old, neu] of Object.entries(staticImgMap)) {
  const count = html.split(old).length - 1;
  if (count === 0) throw new Error(`Pattern not found: ${old}`);
  html = html.split(old).join(neu);
  console.log(`✓ Image.src ${old} (×${count})`);
}

// 11. Dynamic preview image URLs
html = requireReplaced(html,
  '"assets/textures/previews/" + f[p] + ".png"',
  '__TEXURI__["previews/"+f[p]]',
  'previews f[p]'
);
html = requireReplaced(html,
  '"assets/textures/previews/" + h[d] + ".png"',
  '__TEXURI__["previews/"+h[d]]',
  'previews h[d]'
);
console.log('✓ Dynamic preview URLs');

// 12. Chunk mesh builder — uses getMaterialTexture() file path to create texture on-the-fly
//     Replace the BABYLON.Texture(filePath,...) with a lookup into the pre-loaded registry._textures[t]
html = requireReplaced(html,
  'var a = e.rendering.getScene(),\n                                    u = new BABYLON.Texture(n, a, !0, !1, BABYLON.Texture.NEAREST_SAMPLINGMODE);',
  'var a = e.rendering.getScene(),\n                                    u = __mkTerrainTex__(n, a, BABYLON.Texture.NEAREST_SAMPLINGMODE) || new BABYLON.Texture(n, a, !0, !1, BABYLON.Texture.NEAREST_SAMPLINGMODE);',
  'chunk mesh builder terrain texture'
);
console.log('✓ Chunk mesh builder terrain texture');

// ── Verify no remaining assets/textures references (except the texturePath config string) ──
const remaining = (html.match(/assets\/textures\//g) || []).length;
// texturePath: "assets/textures/" appears exactly once (line ~9718) — that's OK, it's metadata
if (remaining > 1) {
  console.warn(`⚠  ${remaining} remaining "assets/textures/" references (expected 1 for texturePath config)`);
  // Print them for debugging
  const lines = html.split('\n');
  lines.forEach((ln, i) => {
    if (ln.includes('assets/textures/')) console.warn(`  line ${i+1}: ${ln.trim().slice(0,120)}`);
  });
} else {
  console.log(`✓ All texture references replaced (${remaining} remaining — texturePath config only)`);
}

// ── Write patched index.html ──────────────────────────────────────────────────
fs.writeFileSync(INDEX_HTML, html, 'utf8');
console.log(`\nWritten index.html: ${originalLen.toLocaleString()} → ${html.length.toLocaleString()} bytes`);

// ── Delete texture files ──────────────────────────────────────────────────────
function deleteDir(dir) {
  if (!fs.existsSync(dir)) return;
  for (const f of fs.readdirSync(dir)) {
    const fp = path.join(dir, f);
    if (fs.statSync(fp).isDirectory()) deleteDir(fp);
    else { fs.unlinkSync(fp); console.log('Deleted:', fp); }
  }
  fs.rmdirSync(dir);
}
deleteDir(TEXTURES_DIR);
console.log('\nAll textures embedded. assets/textures/ deleted.');
console.log('Done!');
