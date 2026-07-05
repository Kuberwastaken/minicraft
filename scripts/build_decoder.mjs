// Build the self-extracting decoder bootstrap for tweet 2.
//   decoder_page.html  (embeds the LZMA engine + UI)  -- inline lzma-d-min.js
//   -> deflate-raw the whole page -> base64
//   -> tiny bootstrap that inflates it with native DecompressionStream and writes it
// Fully offline for decode (LZMA is embedded); only auto-fill/font/wallpaper need the net.
//
// Usage: node scripts/build_decoder.mjs [GH_BASE_URL] [out.html]
import { readFileSync, writeFileSync } from 'node:fs';
import zlib from 'node:zlib';

const GH  = process.argv[2] || 'https://raw.githubusercontent.com/Kuberwastaken/minicraft/main';
const out = process.argv[3] || 'scripts/decoder_bootstrap.html';

let page = readFileSync('scripts/decoder_page.html', 'utf8');
const lzma = readFileSync('scripts/lzma-d-min.js', 'utf8').replace(/<\/script>/g, '<\\/script>');
page = page.replace('__LZMA_SRC__', () => lzma).replace('__GH__', GH);

const deflated = zlib.deflateRawSync(Buffer.from(page, 'utf8'), { level: 9 });
const b64 = deflated.toString('base64');
const boot = '<!doctype html><meta charset="utf-8"><body><script>'
  + '(async function(){var b=atob("' + b64 + '"),u=new Uint8Array(b.length),i=0;'
  + 'for(;i<b.length;i++)u[i]=b.charCodeAt(i);'
  + 'var h=await new Response(new Response(u).body.pipeThrough(new DecompressionStream("deflate-raw"))).text();'
  + 'document.open();document.write(h);document.close()})()</script>';
writeFileSync(out, boot);

// self-check: does the bootstrap's blob inflate back to the exact page?
const roundtrip = zlib.inflateRawSync(Buffer.from(b64, 'base64')).toString('utf8');
const dataUrl = 'data:text/html;base64,' + Buffer.from(boot, 'utf8').toString('base64');
const composeUrl = 'https://x.com/compose/post?text=' + encodeURIComponent(dataUrl);

console.log('decoder page   :', Buffer.byteLength(page).toLocaleString(), 'B (LZMA engine embedded)');
console.log('deflate-raw    :', deflated.length.toLocaleString(), 'B -> base64', b64.length.toLocaleString());
console.log('bootstrap html :', Buffer.byteLength(boot).toLocaleString(), 'B');
console.log('inflate self-check :', roundtrip === page ? 'page reconstructs exactly' : 'MISMATCH');
console.log('compose-link URL   :', composeUrl.length.toLocaleString(), 'chars (cap 10,000)',
  composeUrl.length <= 10000 ? 'FITS (' + (10000 - composeUrl.length) + ' margin)' : 'OVER by ' + (composeUrl.length - 10000));
process.exit(roundtrip === page && composeUrl.length <= 10000 ? 0 : 1);
