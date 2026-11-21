import fs from 'node:fs';
import path from 'node:path';

const backlogPath = path.join(process.cwd(), '.loop/elementor_parity_backlog.json');
const data = JSON.parse(fs.readFileSync(backlogPath, 'utf8'));

const PASSED_IDS = ["EL-W1-042", "EL-W1-043", "EL-W1-044"];

for (const item of data.backlog) {
  if (PASSED_IDS.includes(item.id)) {
    item.passes = true;
    item.lastVerified = new Date().toISOString();
  }
}

fs.writeFileSync(backlogPath, JSON.stringify(data, null, 2), 'utf8');
console.log(`Updated backlog: ${PASSED_IDS.join(', ')} passed.`);
