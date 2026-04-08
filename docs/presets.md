---
layout: default
title: Source Presets
---

# AIRWave

<div id="lang-en" class="lang-section" markdown="1">

## Source Preset Library

AIRWave includes a curated library of information source presets across multiple technology domains. When you run the `airwave-wizard` wizard, it automatically matches sources to your interests.

You can also browse the list below and manually add sources to your `data/config.json`.

---

### 🤖 AI / Machine Learning

| Type | Source | Description |
|------|--------|-------------|
| Reddit | r/MachineLearning | Top ML research discussions |
| Reddit | r/LocalLLaMA | Local LLM community — model releases, benchmarks, deployment tips |
| RSS | Simon Willison | LLM tools and experiments |
| GitHub | @karpathy | AI educator and researcher |
| GitHub | vllm-project/vllm | High-throughput LLM serving engine |

### 🖥️ Systems / Infrastructure

| Type | Source | Description |
|------|--------|-------------|
| RSS | LWN.net | Linux and kernel news |
| Reddit | r/linux | Linux community discussions |
| RSS | Brendan Gregg | Performance and systems |
| GitHub | @torvalds | Linux creator |

### 🔒 Security / Privacy

| Type | Source | Description |
|------|--------|-------------|
| Reddit | r/netsec | Information security community |
| RSS | Krebs on Security | Investigative security journalism |
| RSS | Schneier on Security | Security analysis and commentary |

### 🌐 Web Development

| Type | Source | Description |
|------|--------|-------------|
| Reddit | r/webdev | Web development community |
| Reddit | r/javascript | JavaScript discussions and news |
| RSS | CSS-Tricks | Frontend tips and techniques |

### 🔤 Programming Languages / Compilers

| Type | Source | Description |
|------|--------|-------------|
| Reddit | r/ProgrammingLanguages | Programming language design and theory |
| Reddit | r/rust | Rust programming community |
| GitHub | rust-lang/rust | Rust language releases |
| GitHub | ziglang/zig | Zig language releases |

### 🤖 Embedded / Robotics / Hardware

| Type | Source | Description |
|------|--------|-------------|
| Reddit | r/robotics | Robotics research and projects |
| Reddit | r/embedded | Embedded systems development |
| RSS | Hackaday | Hardware hacking and projects |

### 🛠️ Open Source / DevTools

| Type | Source | Description |
|------|--------|-------------|
| RSS | GitHub Trending | Daily popular repositories |
| Reddit | r/commandline | Command line tools and tips |
| GitHub | neovim/neovim | Neovim editor releases |

### 🔬 Science / Research

| Type | Source | Description |
|------|--------|-------------|
| Reddit | r/science | Science news and discussions |
| RSS | Nature | Latest research highlights |
| RSS | Quanta Magazine | Accessible science journalism |

---

## 🤝 Contribute Your Sources

We welcome community contributions! If you have high-quality sources to share:

1. Fork the [AIRWave repository](https://github.com/solution8-com/AIRWave)
2. Edit `data/presets.json` and add your source under the appropriate domain
3. Submit a Pull Request

**Contribution guidelines**:

- Ensure the source is **actively maintained** and regularly updated
- It should have a **high signal-to-noise ratio**
- Provide both `description` (English)
- Add appropriate `tags` for keyword matching
- Place it under a fitting `domain`, or create a new one

Example format:

```json
{
  "type": "rss",
  "description": "Your source description",
  "tags": ["topic1", "topic2"],
  "config": {
    "name": "Source Name",
    "url": "https://example.com/feed.xml",
    "category": "your-category"
  }
}
```

</div>
