const fs = require("fs");
const user = encodeURIComponent(fs.readFileSync("/run/secrets/root_user", "utf8").trim());
const password = encodeURIComponent(fs.readFileSync("/run/secrets/root_password", "utf8").trim());
try {
  const admin = connect(`mongodb://${user}:${password}@127.0.0.1:27017/admin?directConnection=true&serverSelectionTimeoutMS=2000`);
  const hello = admin.runCommand({hello: 1});
  quit(hello.ok === 1 && hello.setName === "kltn-rs" && hello.isWritablePrimary ? 0 : 1);
} catch (_) {
  quit(1);
}
