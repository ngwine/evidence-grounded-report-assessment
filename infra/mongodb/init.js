const fs = require("fs");
const user = encodeURIComponent(fs.readFileSync("/run/secrets/root_user", "utf8").trim());
const password = encodeURIComponent(fs.readFileSync("/run/secrets/root_password", "utf8").trim());
let complete = false;
for (let attempt = 0; attempt < 60 && !complete; attempt++) {
  try {
    const admin = connect(`mongodb://${user}:${password}@mongo:27017/admin?directConnection=true&serverSelectionTimeoutMS=2000`);
    const hello = admin.runCommand({hello: 1});
    if (hello.setName === "kltn-rs") {
      complete = true;
    } else {
      const result = admin.runCommand({replSetInitiate: {
        _id: "kltn-rs", members: [{_id: 0, host: "mongo:27017"}]
      }});
      complete = result.ok === 1 || result.codeName === "AlreadyInitialized";
    }
  } catch (_) {
    // Credentials, connection strings and server error payloads stay out of logs.
  }
  if (!complete) sleep(2000);
}
print(complete ? "Replica set initialized" : "Replica set initialization failed");
quit(complete ? 0 : 1);
