// See all configuration options: https://remotion.dev/docs/config
// Each option also is available as a CLI flag: https://remotion.dev/docs/cli

// Note: When using the Node.JS APIs, the config file doesn't apply. Instead, pass options directly to the APIs

import fs from "node:fs";
import { Config } from "@remotion/cli/config";

Config.setRspack(true);
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);

// Use a locally installed Chrome Headless Shell when one is present (cloud
// sessions ship one under /opt/pw-browsers). Otherwise Remotion downloads its
// own on first render, which is what happens on a normal computer.
const localBrowser = [
  process.env.REMOTION_BROWSER_EXECUTABLE,
  "/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell",
].find((p) => p && fs.existsSync(p));
if (localBrowser) {
  Config.setBrowserExecutable(localBrowser);
}
