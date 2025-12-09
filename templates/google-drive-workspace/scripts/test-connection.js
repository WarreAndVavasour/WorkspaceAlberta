#!/usr/bin/env node
/**
 * Test Google Drive Connection
 * Verifies that OAuth is set up correctly by listing recent files.
 */

const { google } = require('googleapis');
const fs = require('fs');
const path = require('path');

const TOKEN_PATH = path.join(__dirname, '..', '.credentials', 'google-token.json');

const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
  dim: '\x1b[2m'
};

async function testConnection() {
  console.log('\nTesting Google Drive connection...\n');
  
  // Check token exists
  if (!fs.existsSync(TOKEN_PATH)) {
    console.log(`${colors.red}[ERROR] No authorization token found.${colors.reset}`);
    console.log('Run "npm run setup" first to authorize Google Drive access.\n');
    process.exit(1);
  }
  
  // Load credentials
  const clientId = process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET;
  
  if (!clientId || !clientSecret) {
    console.log(`${colors.red}[ERROR] Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET${colors.reset}`);
    process.exit(1);
  }
  
  // Create OAuth client
  const oauth2Client = new google.auth.OAuth2(clientId, clientSecret);
  const tokens = JSON.parse(fs.readFileSync(TOKEN_PATH, 'utf8'));
  oauth2Client.setCredentials(tokens);
  
  // Create Drive client
  const drive = google.drive({ version: 'v3', auth: oauth2Client });
  
  try {
    // List recent files
    const response = await drive.files.list({
      pageSize: 10,
      fields: 'files(id, name, mimeType, modifiedTime)',
      orderBy: 'modifiedTime desc'
    });
    
    const files = response.data.files;
    
    console.log(`${colors.green}[SUCCESS] Connected to Google Drive!${colors.reset}\n`);
    console.log(`${colors.cyan}Your 10 most recent files:${colors.reset}\n`);
    
    if (files.length === 0) {
      console.log('  (No files found)');
    } else {
      files.forEach((file, i) => {
        const type = getFileType(file.mimeType);
        const date = new Date(file.modifiedTime).toLocaleDateString();
        console.log(`  ${i + 1}. ${file.name}`);
        console.log(`     ${colors.dim}Type: ${type} | Modified: ${date}${colors.reset}`);
      });
    }
    
    console.log(`\n${colors.green}Google Drive is ready to use with your AI assistant!${colors.reset}`);
    console.log('Open the AI chat (Ctrl+Shift+I) and try asking about your files.\n');
    
  } catch (error) {
    console.log(`${colors.red}[ERROR] Failed to connect: ${error.message}${colors.reset}`);
    
    if (error.message.includes('invalid_grant')) {
      console.log('\nYour authorization has expired. Run "npm run setup" to re-authorize.\n');
    }
    process.exit(1);
  }
}

function getFileType(mimeType) {
  const types = {
    'application/vnd.google-apps.document': 'Google Doc',
    'application/vnd.google-apps.spreadsheet': 'Google Sheet',
    'application/vnd.google-apps.presentation': 'Google Slides',
    'application/vnd.google-apps.folder': 'Folder',
    'application/pdf': 'PDF',
    'image/': 'Image',
    'video/': 'Video',
    'audio/': 'Audio'
  };
  
  for (const [key, value] of Object.entries(types)) {
    if (mimeType.includes(key)) return value;
  }
  return 'File';
}

testConnection();
