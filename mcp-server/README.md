# ChatGPT MCP bridge

This local MCP server makes the existing personal-assistant backend available as tools to a compatible ChatGPT custom-app/MCP client. ChatGPT supplies the language model and reasoning; this bridge does not call the OpenAI API.

## Local Windows setup

1. Start the existing backend at `http://127.0.0.1:8000`.
2. From the repository root, create the isolated MCP environment and install dependencies:

   ```powershell
   py -3.12 -m venv mcp-server\.venv
   mcp-server\.venv\Scripts\python.exe -m pip install -r mcp-server\requirements.txt
   ```

3. Configure the MCP client to launch the server over stdio. Use the absolute paths for your machine:

   ```json
   {
     "mcpServers": {
       "my-personal-assistant": {
         "command": "C:\\Users\\YOUR_WINDOWS_USER\\my-ai-personal-assistant\\my-ai-personal-assistant\\mcp-server\\.venv\\Scripts\\python.exe",
         "args": [
           "C:\\Users\\YOUR_WINDOWS_USER\\my-ai-personal-assistant\\my-ai-personal-assistant\\mcp-server\\server.py"
         ],
         "env": {
           "APP_ENV": "development",
           "ASSISTANT_USER_ID": "local-developer",
           "ASSISTANT_API_URL": "http://127.0.0.1:8000",
           "MCP_TRANSPORT": "stdio"
         }
       }
     }
   }
   ```

   Keep this stdio configuration local to your own machine. Do not publish a development identity or expose the backend port to the internet.

4. Restart the MCP client and inspect the available tools. Test `assistant_health` and `list_connected_accounts` first.

## Tools

- Account and health: `assistant_health`, `list_connected_accounts`, `list_integrations`
- Gmail read: `gmail_list_messages`, `gmail_get_message`
- Calendar read/write: `calendar_list_events`, `calendar_create_event`
- Todoist read/write: `todoist_list_tasks`, `todoist_create_task`
- WhatsApp: `list_whatsapp_tools`, `request_whatsapp_permission`, `list_permission_requests`, `call_whatsapp_tool`

The backend remains the authorization source of truth. Calendar and Todoist writes require provider scopes already granted by their OAuth connections. Gmail is currently read-only because the connected Google grant contains `gmail.readonly`; sending email is not exposed. WhatsApp tools require discovery and a separately approved backend scope (read, write, or send). A discovered tool is not automatically authorized.

Configure ChatGPT app permissions to ask before write/send actions. Confirm the exact recipient, content, event, or task before invoking any write tool. Do not grant WhatsApp send permission unless you intend to enable message sending.

## ChatGPT account availability

ChatGPT must support custom MCP apps for the intended connection method. OpenAI's current help documentation lists custom remote MCP connections with full read/write support for Business and Enterprise/Edu; Pro supports read/fetch connections, and Free does not have the documented custom MCP connection feature. ChatGPT's client-specific local-app support may also depend on the installed desktop client and account/workspace controls. Check the current account UI before assuming the server can be added.

For a remote ChatGPT web connection, the MCP endpoint must be reachable over HTTPS. Do not expose this development server or its development identity directly to the public internet. A production deployment needs HTTPS, per-user OAuth/OIDC identity mapping, short-lived tokens, and security review.

## No model API usage

These MCP tools call only the user's local backend provider endpoints. They do not call `/api/v1/chat` and do not use `OPENAI_API_KEY`. The existing dashboard's own AI chat endpoint still uses that key; leave it unused or disable it separately if you want to prevent all API-based model calls.
