// Read the installed distribution, not the older source checkout.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = 'D:/deepseek/resources/app.asar/dsh/node_modules/@deepseek-ai';
const out = path.resolve(__dirname, '../state/mode-inspection');
fs.mkdirSync(out, {recursive: true});
const files = ['dsh-base/cordis.patch.yml', 'dsh-sdk-app/cordis.patch.yml', 'dsh-web-app/cordis.patch.yml',
  ...['standard','minimal','ptc','cordis'].map(id => `dsh-web-app/presets/${id}.patch.yml`)];
const records = [];
for (const name of files) {
  const text = fs.readFileSync(path.join(root, name), 'utf8');
  const target = path.join(out, name.replaceAll('/', '__'));
  fs.writeFileSync(target, text);
  records.push({source: name, saved: target, sha256: crypto.createHash('sha256').update(text).digest('hex')});
}
fs.writeFileSync(path.join(out, 'manifest.json'), JSON.stringify(records, null, 2));
console.log(JSON.stringify(records));
