# Telora — Multi-Agent RAG Application

An agentic retrieval-augmented generation (RAG) customer-support application
powered by OpenAI's `gpt-4o-mini` model. Telora routes each question across
specialized Router, Activation FAQ, and Other FAQ agents, grounding responses
in a searchable telecom FAQ knowledge base.

## Setup

Install the dependencies with `uv`:

```powershell
uv sync
```

Create a `.env` file in the project root and add your OpenAI API key:

```dotenv
OPENAI_API_KEY=your-api-key
CHAT_ENCRYPTION_KEY=your-fernet-key
```

Generate `CHAT_ENCRYPTION_KEY` with:

```powershell
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The `.env` file is ignored by Git. The app uses separate Router, Activation FAQ,
and Other FAQ agents, with UUID-based SQLite checkpoints. Only customer name,
mobile number, and address fields are encrypted in checkpoint storage.

FAQ embeddings use `text-embedding-3-small` by default and are cached in
`faq_vectors.sqlite`. The app reconciles the cache against
`mock_telecom_faq.json` using content hashes and only regenerates changed FAQ
records. Use **Refresh FAQ embeddings** in the sidebar to force a rebuild.

## Run

```powershell
uv run streamlit run app.py
```

Type a prompt in the chatbox to display the model response below it.
