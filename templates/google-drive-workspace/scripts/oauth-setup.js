#!/usr/bin/env node
/**
 * Google Drive OAuth Setup Wizard
 * 
 * This script walks users through authorizing Google Drive access.
 * It starts a local server to handle the OAuth callback.
 */

const { google } = require('googleapis');
const express = require('express');
const fs = require('fs');
const path = require('path');
const open = require('open');

// Configuration
const TOKEN_PATH = path.join(__dirname, '..', '.credentials', 'google-token.json');
const SCOPES = [
  'https://www.googleapis.com/auth/drive.readonly',
  'https://www.googleapis.com/auth/drive.metadata.readonly'
];

// Colors for terminal output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m'
};

function log(message, color = '') {
  console.log(`${color}${message}${colors.reset}`);
}

function checkSecrets() {
  const clientId = process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET;
  
  if (!clientId || !clientSecret) {
    log('\n[ERROR] Missing Google credentials!', colors.red);
    log('\nPlease add these secrets to your GitHub Codespaces settings:', colors.yellow);
    log('  1. Go to: https://github.com/settings/codespaces');
    log('  2. Add GOOGLE_CLIENT_ID');
    log('  3. Add GOOGLE_CLIENT_SECRET');
    log('  4. Rebuild this Codespace');
    log('\nSee SETUP-GUIDE.md for detailed instructions.\n');
    process.exit(1);
  }
  
  return { clientId, clientSecret };
}

async function runOAuthFlow() {
  log('\n========================================', colors.cyan);
  log('  Google Drive OAuth Setup Wizard', colors.bright);
  log('========================================\n', colors.cyan);
  
  // Check for credentials
  const { clientId, clientSecret } = checkSecrets();
  log('[OK] Found Google credentials', colors.green);
  
  // Check if already authorized
  if (fs.existsSync(TOKEN_PATH)) {
    log('[OK] Found existing authorization token', colors.green);
    log('\nYou are already authorized! Run "npm run test-drive" to verify.\n');
    
    const readline = require('readline');
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });
    
    const answer = await new Promise(resolve => {
      rl.question('Do you want to re-authorize? (y/N): ', resolve);
    });
    rl.close();
    
    if (answer.toLowerCase() !== 'y') {
      log('\nKeeping existing authorization.\n');
      process.exit(0);
    }
  }
  
  // Create OAuth2 client
  const redirectUri = 'http://localhost:3000/callback';
  const oauth2Client = new google.auth.OAuth2(clientId, clientSecret, redirectUri);
  
  // Generate auth URL
  const authUrl = oauth2Client.generateAuthUrl({
    access_type: 'offline',
    scope: SCOPES,
    prompt: 'consent'
  });
  
  log('\n[STEP 1] Opening browser for authorization...', colors.yellow);
  log('\nIf the browser does not open, visit this URL:', colors.cyan);
  log(authUrl);
  log('');
  
  // Start local server to receive callback
  const app = express();
  let server;
  
  const authPromise = new Promise((resolve, reject) => {
    app.get('/callback', async (req, res) => {
      const code = req.query.code;
      
      if (!code) {
        res.send('<h1>Error: No authorization code received</h1>');
        reject(new Error('No authorization code'));
        return;
      }
      
      try {
        log('[STEP 2] Received authorization code, exchanging for tokens...', colors.yellow);
        
        const { tokens } = await oauth2Client.getToken(code);
        oauth2Client.setCredentials(tokens);
        
        // Save token
        const tokenDir = path.dirname(TOKEN_PATH);
        if (!fs.existsSync(tokenDir)) {
          fs.mkdirSync(tokenDir, { recursive: true });
        }
        fs.writeFileSync(TOKEN_PATH, JSON.stringify(tokens, null, 2));
        
        res.send(`
          <html>
            <head>
              <style>
                body { font-family: system-ui; max-width: 600px; margin: 100px auto; text-align: center; }
                h1 { color: #10B981; }
                p { color: #6B7280; }
              </style>
            </head>
            <body>
              <h1>Authorization Successful!</h1>
              <p>You can close this window and return to your Codespace.</p>
              <p>Run <code>npm run test-drive</code> to verify the connection.</p>
            </body>
          </html>
        `);
        
        resolve(tokens);
      } catch (error) {
        res.send(`<h1>Error: ${error.message}</h1>`);
        reject(error);
      }
    });
    
    server = app.listen(3000, () => {
      log('[OK] Local callback server running on port 3000', colors.green);
    });
  });
  
  // Open browser
  try {
    await open(authUrl);
  } catch (e) {
    log('Could not open browser automatically. Please visit the URL above.', colors.yellow);
  }
  
  // Wait for authorization
  try {
    await authPromise;
    log('\n[OK] Authorization successful!', colors.green);
    log('[OK] Token saved to .credentials/google-token.json', colors.green);
    log('\n========================================', colors.cyan);
    log('  Setup Complete!', colors.bright);
    log('========================================', colors.cyan);
    log('\nNext steps:');
    log('  1. Run: npm run test-drive');
    log('  2. Open AI chat (Ctrl+Shift+I)');
    log('  3. Ask about your Google Drive files!\n');
  } catch (error) {
    log(`\n[ERROR] Authorization failed: ${error.message}`, colors.red);
    process.exit(1);
  } finally {
    server.close();
  }
}

runOAuthFlow();
