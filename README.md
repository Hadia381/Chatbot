# 🤖 Multi-Company Chatbot

This project is an AI-powered chatbot that answers user questions about various companies. It uses stored company information (like About, Products, and Services) from a database and builds intelligent responses using OpenAI's language models. Just specify the company name, ask your question, and the chatbot will respond with helpful details!

---

## 🚀 Features

- Add and manage multiple company profiles via API.
- Uses company-specific context to generate human-like responses.
- Supports greetings, follow-up queries, and farewell messages.
- Remembers previous chat topics (like products or services) for follow-up handling.
- Logs all queries and responses for later reference.

---

## 🧠 How It Works

- You store company details like:
  - Name
  - Type
  - About
  - Products
  - Services
  - Links
- The chatbot constructs a dynamic prompt using this information.
- OpenAI GPT processes the prompt and query history to return a response.
- Follows friendly, short, and company-aware response patterns.

> 📌 Note: This is not a RAG system — it uses dynamic prompt construction with OpenAI.
