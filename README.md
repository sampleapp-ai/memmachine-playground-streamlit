---
title: 🧠 MemMachine Playground – AI Memory for LLMs & Agents
emoji: 🧠
colorFrom: green
colorTo: gray
sdk: docker
pinned: true
short_description: Official MemMachine playground for AI, agent memory for LLMs
app_port: 7860
hf_oauth: true
hf_oauth_scopes:
- email
hf_oauth_authorized_org:
- Memverge
tags:
- ai-memory
- persistent-memory
- agent-memory
- multi-llm
- llm-playground
- ai-agents
- memory
- chatbot
- open-source
- agents
license: apache-2.0
---

# 🧠 MemMachine Playground

**This is the official interactive playground for MemMachine (memmachine.ai) — the universal memory layer for AI agents**

A powerful playground for experimenting with various Large Language Models (LLMs) enhanced by MemMachine's persistent memory system. Compare conversations with and without memory to see how AI memory transforms your interactions.

## ✨ Features

- **Multiple LLM Providers**: OpenAI, Anthropic (Claude), AWS Bedrock and more
- **Persistent Memory**: AI remembers your conversations across sessions
- **Profile Memory**: Builds a personalized profile of you over time
- **Episodic Memory**: Remembers specific conversations and context
- **Secure Authentication**: Token-based authentication to protect your memories
- **Session Management**: Create and manage multiple conversation sessions

## 🚀 Getting Started

### Step 1: Create a Hugging Face Read Token

To authenticate and access your personalized memories, you'll need a Hugging Face access token:

1. **Go to Hugging Face Settings**
   - Visit: https://huggingface.co/settings/tokens
   - Or click your profile → Settings → Access Tokens

2. **Create a New Token**
   - Click **"New token"** button
   - **Name**: Enter a descriptive name (e.g., "MemMachine Playground")
   - **Role**: Select **"Read"** (this is sufficient for authentication)
   - Click **"Generate token"**

3. **Copy Your Token**
   - ⚠️ **Important**: Copy the token immediately (it starts with `hf_`)
   - You won't be able to see it again after closing the page
   - Store it securely

### Step 2: Authenticate in the App

1. **Open the Playground**
   - The app will prompt you to authenticate on first use

2. **Enter Your Token**
   - Paste your Hugging Face Read token in the authentication field
   - Click **"Authenticate"**
   - Your username will be automatically detected and locked

3. **Start Chatting**
   - Your memories are now personalized to your account
   - All conversations are stored securely under your username

## 💡 How to Use

### Basic Usage

1. **Choose a Model**
   - Select from the dropdown in the sidebar
   - Models include GPT-4, Claude, Bedrock, and more

2. **Start a Conversation**
   - Type your message in the chat input
   - The AI will respond using your memory context

3. **Compare with Memory**
   - Toggle "Compare with Control persona" to see responses with/without memory
   - See how memory enhances the AI's understanding

## 🔍 Keywords (for discoverability)

**Core concepts**
- AI memory
- Persistent memory for LLMs
- Agent memory
- Memory for AI agents

**Use cases**
- AI agents with memory
- Long-term memory for LLMs

**Product & platform**
- Multi-LLM playground
- MemMachine AI memory
- LLM memory

### Advanced Features

- **Multiple Sessions**: Create different conversation sessions for different topics
- **Persona Selection**: Test with different user personas (Charlie, Jing, Charles, Control)
- **Profile Management**: View and delete your AI profile when needed
- **Memory Search**: The AI searches your past conversations for relevant context

## 🔒 Security & Privacy

- **Token Authentication**: Your Hugging Face token is used only to identify your username
- **Session-Only Storage**: Tokens are stored only in your browser session
- **Isolated Memories**: Each user's memories are completely isolated
- **No Token Sharing**: Your token is never shared or stored permanently

## 🏗️ Architecture

- **Frontend**: Streamlit (runs in this Hugging Face Space)
- **Backend**: MemMachine server running on EC2
- **Memory Storage**: Neo4j (graph) + Postgres (vector search)
- **Authentication**: Hugging Face token-based authentication

## 📝 Notes

- **Token Expiration**: Read tokens don't expire automatically - they remain valid until you revoke them
- **Memory Persistence**: Your memories are tied to your username, not your token. You can create new tokens without losing memories
- **Rate Limiting**: The backend implements rate limiting (50 requests/minute) to prevent abuse

## 🆘 Troubleshooting

**"Invalid token" error?**
- Make sure you copied the entire token (including `hf_` prefix)
- Verify the token has "Read" permissions
- Try creating a new token if the issue persists

**Can't see my memories?**
- Ensure you're authenticated with the same username
- Memories are stored per username, not per token

**Need help?**
- Check that your token has Read permissions
- Verify you're using a valid Hugging Face account

---

**Powered by [MemMachine](https://github.com/memverge/memmachine)** 🧠# memmachine-playground-streamlit
