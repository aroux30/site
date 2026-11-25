const fs = require("fs");
const text = Buffer.from(process.argv[2], "base64").toString("utf8");
fs.appendFileSync(process.argv[3], text, "utf8");
