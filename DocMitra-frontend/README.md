# DocMitra Frontend

React + Vite frontend starter for the DocMitra application assistant.

## Run locally

```bash
npm install
npm run dev
```

## File structure

- `src/main.jsx` only mounts the React app.
- `src/App.jsx` contains the DocMitra dashboard.
- `src/Chatbot.jsx` contains the chatbot UI and API request.
- `src/Chatbot.css` styles the chatbot.
- `src/styles.css` styles the dashboard.

## Chat API contract

By default, the chatbot sends:

`POST http://127.0.0.1:8000/api/chat/`

JSON body:

```json
{ "message": "What documents are required?" }
```

Expected JSON response:

```json
{ "answer": "Check the requirements in the official notice..." }
```

To configure a different endpoint, create a `.env` file in the project root:

```env
VITE_CHAT_API_URL=http://127.0.0.1:8000/api/chat/
```

The endpoint shown is a placeholder contract; connect it to the actual Django route in the repository. Configure Django CORS/CSRF as appropriate. Document processing shown in this frontend is a demo simulation until connected to real backend APIs.
