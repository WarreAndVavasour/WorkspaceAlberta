# Google Drive MCP Setup Guide

Welcome! This workspace will walk you through connecting Google Drive to your AI assistant.

**Time needed:** 10-15 minutes

---

## Step 1: Create Google Cloud Credentials

You need OAuth credentials from Google Cloud Console.

### 1.1 Open Google Cloud Console

Click this link to open Google Cloud Console:

**[Open Google Cloud Console](https://console.cloud.google.com/apis/credentials)**

### 1.2 Create a New Project (if needed)

1. Click the project dropdown at the top
2. Click "New Project"
3. Name it something like "My AI Workspace"
4. Click "Create"

### 1.3 Enable Google Drive API

1. Go to: **[Enable Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)**
2. Click "Enable"

### 1.4 Create OAuth Credentials

1. Go to: **[Create Credentials](https://console.cloud.google.com/apis/credentials/oauthclient)**
2. If prompted, configure the OAuth consent screen:
   - Choose "External" user type
   - Fill in app name (e.g., "My AI Workspace")
   - Add your email for support contact
   - Click "Save and Continue" through the steps
3. Back at credentials, click "Create Credentials" > "OAuth client ID"
4. Choose "Web application"
5. Add this redirect URI: `http://localhost:3000/callback`
6. Click "Create"
7. **Copy your Client ID and Client Secret** - you'll need them next!

---

## Step 2: Add Your Credentials to GitHub

Now add your credentials as GitHub Codespaces secrets.

### 2.1 Open GitHub Secrets Settings

Click here: **[GitHub Codespaces Secrets](https://github.com/settings/codespaces)**

### 2.2 Add GOOGLE_CLIENT_ID

1. Click "New secret"
2. Name: `GOOGLE_CLIENT_ID`
3. Value: *paste your Client ID from Google*
4. Repository access: Select this repository (or "All repositories")
5. Click "Add secret"

### 2.3 Add GOOGLE_CLIENT_SECRET

1. Click "New secret"
2. Name: `GOOGLE_CLIENT_SECRET`
3. Value: *paste your Client Secret from Google*
4. Repository access: Same as above
5. Click "Add secret"

---

## Step 3: Restart Your Codespace

For the secrets to take effect, you need to restart:

1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type "Codespaces: Rebuild Container"
3. Press Enter
4. Wait for the rebuild (1-2 minutes)

---

## Step 4: Complete OAuth Authorization

After restart, run the setup wizard:

```bash
# In the terminal, run:
npm run setup
```

This will:
1. Open a browser window
2. Ask you to sign into Google
3. Authorize access to your Drive
4. Save the authorization token locally

---

## Step 5: Verify It Works

Test that everything is connected:

```bash
# List your Google Drive files
npm run test-drive
```

You should see a list of files from your Google Drive!

---

## Step 6: Start Using AI with Google Drive

Now you can chat with the AI about your Google Drive:

1. Press `Ctrl+Shift+I` to open the AI chat
2. Try asking:
   - "List my recent Google Drive files"
   - "Find all spreadsheets in my Drive"
   - "Create a new folder called 'AI Projects'"

---

## Troubleshooting

### "Secrets not found" error

- Make sure you added both secrets in GitHub settings
- Make sure you rebuilt the Codespace after adding secrets
- Check that repository access is correct for the secrets

### "Invalid redirect URI" error

- Go back to Google Cloud Console
- Edit your OAuth client
- Make sure the redirect URI is exactly: `http://localhost:3000/callback`

### "Access denied" error

- In Google Cloud Console, add your email to "Test users"
- Or publish the OAuth consent screen (for production use)

---

## What's Next?

Once Google Drive is connected, you can:

1. **Add more tools** - See `templates/` for Stripe, Calendar, etc.
2. **Customize your workspace** - Edit `.vscode/mcp.json`
3. **Share with your team** - They can create their own workspace from your template

---

## Need Help?

- Check `docs/` folder for more guides
- Email: support@workspacealberta.com
