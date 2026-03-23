# Google Drive MCP Server — One-Time Setup

This project uses the [Google Drive MCP server](https://www.npmjs.com/package/@modelcontextprotocol/server-gdrive) so Cursor can search and read files from the **MVP** Drive folder (Biology, Chemistry, Physics, Open Source Textbooks). Config is in [.cursor/mcp.json](mcp.json).

## 1. Google Cloud setup

1. [Create a new Google Cloud project](https://console.cloud.google.com/projectcreate).
2. [Enable the Google Drive API](https://console.cloud.google.com/workspace-api/products).
3. [Configure the OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent) (e.g. **Internal** for testing).
4. Add OAuth scope: `https://www.googleapis.com/auth/drive.readonly`.
5. [Create an OAuth Client ID](https://console.cloud.google.com/apis/credentials/oauthclient) for application type **Desktop App**.
6. Download the client JSON and rename it to `gcp-oauth.keys.json`.

## 2. Where to put the keys

Place `gcp-oauth.keys.json` where the server can find it. When using NPX, the server often looks in the **project root** (the directory Cursor opens as the workspace). Put the file in the IBrary project root and ensure it is listed in [.gitignore](../.gitignore) so it is never committed.

If you prefer to keep keys under `.cursor/`, use `.cursor/gcp-oauth.keys.json` and add that path to `.gitignore`. The server may require an environment variable to point to this path; check the package README for supported env vars.

## 3. One-time authentication

Run the server’s auth flow once so it can store credentials:

- From the **project root**, run:  
  `npx -y @modelcontextprotocol/server-gdrive auth`  
  (if the package supports an `auth` subcommand), or follow the [server’s README](https://www.npmjs.com/package/@modelcontextprotocol/server-gdrive).
- Complete the sign-in in your browser.
- Credentials are typically saved as `.gdrive-server-credentials.json` in the project root or current working directory. Add this file to `.gitignore`.

## 4. MVP folder ID

The MVP Drive folder used for this project is:

- **URL:** [https://drive.google.com/drive/folders/1mrSVxPNVhDfBgXpRfWdoinePl-SjTcRb](https://drive.google.com/drive/folders/1mrSVxPNVhDfBgXpRfWdoinePl-SjTcRb)
- **Folder ID:** `1mrSVxPNVhDfBgXpRfWdoinePl-SjTcRb`

Use this ID when searching or opening files in that folder (e.g. “list files in folder 1mrSVxPNVhDfBgXpRfWdoinePl-SjTcRb”, or open `gdrive:///<file_id>` for a file inside it).

## 5. Restart Cursor

After creating or editing [.cursor/mcp.json](mcp.json), fully quit and restart Cursor for the MCP server to load.
