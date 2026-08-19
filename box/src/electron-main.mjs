/**
 * Thin optional window chrome. Install Electron only when you want a native
 * window: `npx electron src/electron-main.mjs`
 */
import { ABOUT_BODY, ABOUT_TITLE, APP_NAME, TRAY_TOOLTIP, VENDOR, WINDOW_TITLE } from "./branding.mjs";
import { defaultConfig } from "./config.mjs";
import { startUiServer } from "./ui-server.mjs";

async function main() {
  const { app, BrowserWindow, Menu, Tray, nativeImage, dialog } = await import("electron");

  const config = defaultConfig();
  const { url } = await startUiServer({
    port: config.uiPort,
    mcpUrl: config.mcpUrl,
  });

  await app.whenReady();
  app.setName(APP_NAME);
  if (app.setAboutPanelOptions) {
    app.setAboutPanelOptions({
      applicationName: ABOUT_TITLE,
      applicationVersion: config.clientVersion,
      copyright: VENDOR,
      credits: ABOUT_BODY,
    });
  }

  const window = new BrowserWindow({
    title: WINDOW_TITLE,
    width: 980,
    height: 720,
    minWidth: 720,
    minHeight: 520,
    autoHideMenuBar: true,
    webPreferences: {
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  await window.loadURL(url);

  const tray = new Tray(nativeImage.createEmpty());
  tray.setToolTip(TRAY_TOOLTIP);
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: APP_NAME, enabled: false },
      {
        label: "About",
        click: () => {
          dialog.showMessageBox({
            type: "info",
            title: ABOUT_TITLE,
            message: ABOUT_TITLE,
            detail: ABOUT_BODY,
          });
        },
      },
      { type: "separator" },
      { label: "Quit", click: () => app.quit() },
    ]),
  );

  app.on("window-all-closed", () => app.quit());
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
