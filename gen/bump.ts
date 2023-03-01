import { execSync, exec } from "child_process";
import { readFile, writeFile } from "fs/promises";
import util from "util";
const execAsync = util.promisify(exec);

(async () => {
  const pathToReadFrom = "../frontend/src/gen-types.ts";
  const pathToWriteTo = "../frontend/src/gen-types-camel.ts";
  await execAsync(
    `npx openapi-typescript https://raw.githubusercontent.com/uselotus/lotus/main/docs/openapi.yaml --output ${pathToReadFrom}`
  );

  let result = "";
  try {
    // Convert the generated code to use camel case naming
    const res = await readFile(pathToReadFrom, { encoding: "utf-8" });
    result = res.replace(/([a-z0-9])(_[a-z0-9])/g, (_, p1, p2) => {
      return p1 + p2.toUpperCase().substr(1);
    });
  } catch (error) {
    console.error(
      `An error occurred reading from ${pathToReadFrom} & converting to camel case`,
      error
    );
  }
  try {
    await writeFile(pathToWriteTo, result, { encoding: "utf-8" });
  } catch (error) {
    console.error(`Something went wrong writing to ${pathToWriteTo}`, error);
  }
})();
