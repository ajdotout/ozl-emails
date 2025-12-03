import * as React from "react";
import { render } from "@react-email/render";
import { mkdirSync, writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { DeveloperNotification } from "./templates/DeveloperNotification";
import { OutreachMarketing } from "./templates/OutreachMarketing";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const distDir = join(__dirname, "..", "dist");

mkdirSync(distDir, { recursive: true });

async function writeTemplate(name: string, component: React.ReactElement) {
  const html = await render(component, { pretty: true });
  const text = await render(component, { plainText: true });

  writeFileSync(join(distDir, `${name}.html`), html, "utf8");
  writeFileSync(join(distDir, `${name}.txt`), text, "utf8");
}

// Register templates here so they are built into dist/.
await writeTemplate("developer-notification", <DeveloperNotification />);
await writeTemplate("outreach-marketing", <OutreachMarketing />);


