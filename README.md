# ⚡ 𝗧𝗘𝗫𝗧-𝗟𝗘𝗘𝗖𝗛 & 𝗖𝗟𝗔𝗦𝗦𝗣𝗟𝗨𝗦 𝗗𝗥𝗠 𝗕𝗢𝗧 ⚡

A high-performance Telegram Video Leech & DRM Decryption Bot built with **Pyrogram**, **yt-dlp**, and **pywidevine**. Supports batch downloading from `.txt` files and direct single-video downloading using Classplus Token & `contentHashId`.

---

## 🌟 Key Features

- 📁 **Batch File Leeching (`/upload`)**: Upload a `.txt` file containing hundreds of video/PDF links and download them sequentially.
- ⚡ **Classplus & DRM Engine (`/cp`)**: Direct single-video download by simply providing `x-access-token` and `contentHashId` or Classplus URL.
- 🔐 **Widevine DRM Decryption**: Built-in support for extracting PSSH and Widevine decryption keys (`--key kid:key`) using `.wvd` device profiles.
- 🚀 **High Speed**: Accelerated multi-connection downloads using `aria2c` and `yt-dlp`.
- 📊 **Real-Time Progress Bar**: Displays live download and upload speed, percentage, ETA, and processed size.
- 🎯 **Multi-Platform Support**:
  - Classplus (`cpvod.testbook.com`, `media-cdn.classplusapp.com`, `tencdn.classplusapp.com`, Akamai L1/L2)
  - Physics Wallah (`d1d34p8vz63oiq`, `sec1.pw.live`)
  - VisionIAS (`playlist.m3u8`)
  - CloudFront HLS & Master MPD
  - Google Drive & YouTube
  - Direct MP4 & PDF links

---

## 🤖 Bot Commands

### 👤 User Commands (Visible to all users)
| Command | Description |
| :--- | :--- |
| `/start` | Start the bot and view available options. |
| `/help` | Detailed guide with examples for all platforms. |
| `/myplan` | Check your membership plan, downloads used, and remaining free quota. |
| `/dl` or `/download` | Direct single-link download (or just paste link directly in chat). |
| `/upload` | Start batch download from a `.txt` file (or just send .txt file). |
| `/cp` or `/classplus` | Direct Classplus video download with Token & `contentHashId` / URL. |

### 👑 Admin Commands (Visible ONLY to Admins & Owner)
| Command | Description | Example |
| :--- | :--- | :--- |
| `/addpaid <user_id> [days]` | Grant Paid Membership for N days (Default: 30) | `/addpaid 123456789 30` |
| `/rempaid <user_id>` | Remove Paid Membership from a user | `/rempaid 123456789` |
| `/resetlimit <user_id>` | Reset user's downloaded count back to 0 | `/resetlimit 123456789` |
| `/status <user_id>` | Inspect any user's membership and download stats | `/status 123456789` |
| `/paidusers` | List all active paid members | `/paidusers` |
| `/stop` | Restart the bot process | `/stop` |

---

## 🔑 Environment Variables

Configure these variables before running the bot:

| Variable | Required | Description | Example |
| :--- | :---: | :--- | :--- |
| `API_ID` | **Yes** | Your Telegram API ID from [my.telegram.org](https://my.telegram.org) | `29719806` |
| `API_HASH` | **Yes** | Your Telegram API Hash from [my.telegram.org](https://my.telegram.org) | `c8e87805739aa77bd5bd...` |
| `BOT_TOKEN` | **Yes** | Bot token obtained from [@BotFather](https://t.me/BotFather) | `7123456789:AAF...` |
| `OWNER_ID` | Recommended | Telegram user ID of the Bot Owner / Primary Admin | `123456789` |
| `ADMINS` | No | Additional Admin IDs separated by spaces | `123456789 987654321` |
| `FREE_LIMIT` | No | Maximum free video downloads allowed for free users (Default: `5`) | `5` |
| `PORT` | No | Port for the built-in keep-alive web server (Default: `8870` or `8080`) | `8080` |
| `WEBHOOK` | No | Keep `True` to enable dummy HTTP server for cloud platforms (Render/Heroku) | `True` |

> [!TIP]
> You can set these in your hosting dashboard under **Environment Variables**, or in `modules/vars.py` directly for local testing.

---

## 🚀 Deployment Guides

---

### 1. 🟣 Deploy on Render.com (Recommended - Free Web Service)

Render allows you to run Dockerized applications with automatic builds:

1. **Fork or Push** this repository to your GitHub account.
2. Sign in to [Render.com](https://render.com).
3. Click **New +** and select **Web Service**.
4. Connect your GitHub repository.
5. In the configuration settings:
   - **Name**: `text-leech-bot` (or any name)
   - **Region**: Choose the closest region (e.g. Singapore or Frankfurt)
   - **Environment**: **`Docker`** (Render will automatically detect the `Dockerfile`)
   - **Plan**: **Free**
6. Scroll down to **Environment Variables** and add:
   - `API_ID` = `Your_Telegram_Api_ID`
   - `API_HASH` = `Your_Telegram_Api_Hash`
   - `BOT_TOKEN` = `Your_Telegram_Bot_Token`
   - `PORT` = `8080`
   - `WEBHOOK` = `True`
7. Click **Create Web Service**.
8. Once built and deployed, your bot will be live 24/7!

---

### 2. 🔴 Deploy on Heroku

Heroku allows you to host the bot easily using its **Container (Docker) stack** so that all required tools (`N_m3u8DL-RE`, `mp4decrypt`, `ffmpeg`, and Widevine tools) run out of the box without any missing dependency.

---

#### 🌐 Method A: Deploy via Heroku Web Dashboard (No Coding / CLI Needed)

1. **Push to GitHub**:
   Make sure you have pushed all the files from this folder to your GitHub repository.

2. **Create New Heroku App**:
   - Go to [dashboard.heroku.com](https://dashboard.heroku.com/) and sign in.
   - Click the **New** button in the top-right corner and select **Create new app**.
   - Give your app a unique name (e.g., `my-ultimate-leech-bot`) and select your region (United States or Europe).
   - Click **Create app**.

3. **Set Container Stack**:
   - Open your terminal / CMD and set the stack to container:
     ```bash
     heroku stack:set container -a your-app-name
     ```
   *(Note: This ensures Heroku builds using the included [heroku.yml](file:///c:/Users/Dell/Desktop/Cp-Api-main/Mtprs-main/heroku.yml) and [Dockerfile](file:///c:/Users/Dell/Desktop/Cp-Api-main/Mtprs-main/Dockerfile) with all Linux DRM tools).*

4. **Add Environment Variables (Config Vars)**:
   - In your Heroku app dashboard, click on the **Settings** tab.
   - Scroll down to **Config Vars** and click **Reveal Config Vars**.
   - Add the following keys and values:
     | KEY | VALUE |
     | :--- | :--- |
     | `API_ID` | `Your Telegram API ID` |
     | `API_HASH` | `Your Telegram API Hash` |
     | `BOT_TOKEN` | `Your Bot Token from @BotFather` |
     | `WEBHOOK` | `True` |

5. **Connect GitHub and Deploy**:
   - Click on the **Deploy** tab.
   - Under **Deployment method**, select **GitHub**.
   - Connect your GitHub account and search for your repository name.
   - Click **Connect** next to your repository.
   - Scroll down to **Manual deploy**, select the `main` branch, and click **Deploy Branch**.
   - Wait 2–3 minutes for Heroku to build the Docker container and install the tools.

6. **Turn ON the Dyno (CRITICAL STEP)**:
   - Once deployment says *Build Succeeded*, go to the **Resources** tab at the top.
   - Under **Free / Eco Dynos**, you will see **`worker`** (or `web`).
   - Click the **pencil icon ✏️** on the right side.
   - Toggle the switch to **ON** (Blue) and click **Confirm**.

7. **Verify Bot is Running**:
   - Click **More** (top right) -> **View logs**.
   - You should see:
     ```text
     [Telegram Bot] Connected to Telegram API successfully!
     [Web Server] Started HTTP server on port ... for Render/Heroku uptime
     ```
   - Go to Telegram and type `/start` in your bot!

---

#### 💻 Method B: Deploy via Heroku CLI (Fastest for Developers)

Run these commands in your project folder (`Mtprs-main`):

```bash
# 1. Log in to Heroku CLI
heroku login

# 2. Create a new Heroku app with container stack
heroku create your-app-name --stack container

# 3. Add your Telegram credentials as config variables
heroku config:set API_ID="your_api_id" -a your-app-name
heroku config:set API_HASH="your_api_hash" -a your-app-name
heroku config:set BOT_TOKEN="your_bot_token" -a your-app-name
heroku config:set WEBHOOK="True" -a your-app-name

# 4. Push the code to Heroku Git to build
git push heroku main

# 5. Scale up the worker dyno to start the bot
heroku ps:scale worker=1 -a your-app-name

# 6. View live logs to check bot status
heroku logs --tail -a your-app-name
```

---

#### 🔘 Method C: 1-Click Heroku Deploy Button

Add this button to your repository README to deploy with a single click:

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

---

#### ⚠️ Heroku Troubleshooting Tips

- **Dyno Stopped / Bot Not Responding**: Make sure you toggled the worker dyno **ON** in the **Resources** tab. By default, Heroku leaves dynos turned off after the first build.
- **Port Binding Error on Web Dyno**: If you use the `web` dyno instead of `worker`, the bot already binds to Heroku's `$PORT` dynamically, so web dynos work seamlessly as well.
- **Viewing Errors**: Run `heroku logs --tail -a your-app-name` to inspect live logs.

---

### 3. 🚂 Deploy on Railway.app

Railway provides ultra-fast Docker deployment:

1. Sign in to [Railway.app](https://railway.app).
2. Click **+ New Project** -> **Deploy from GitHub repo**.
3. Select your repository.
4. Go to the **Variables** tab and add:
   - `API_ID` : `Your_API_ID`
   - `API_HASH` : `Your_API_HASH`
   - `BOT_TOKEN` : `Your_BOT_TOKEN`
   - `PORT` : `8080`
   - `WEBHOOK` : `True`
5. Railway automatically builds using the provided `Dockerfile`.
6. Once deployed, check the deployment logs to confirm bot startup.

---

### 4. 💻 Deploy on Localhost (Windows / Linux / macOS)

#### Prerequisites:
- Python 3.9, 3.10, or 3.11 installed
- `ffmpeg` and `aria2` installed and added to your system PATH

#### Setup Steps:

1. **Clone or navigate to the project directory**:
   ```bash
   cd Mtprs-main
   ```

2. **Create and activate a virtual environment**:
   - **Windows**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - **Linux / macOS**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your credentials**:
   Edit `modules/vars.py` and put your `API_ID`, `API_HASH`, and `BOT_TOKEN`:
   ```python
   API_ID    = "12345678"
   API_HASH  = "abcdef0123456789abcdef0123456789"
   BOT_TOKEN = "1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ"
   ```

5. **Start the Bot**:
   ```bash
   python modules/main.py
   ```

---

### 5. 🟡 Deploy on Google Colab

You can run the bot for free on Google Colab using the included notebook:

1. Go to [Google Colab](https://colab.research.google.com/).
2. Click **File** -> **Upload Notebook** and upload `text_leech_bot` (or rename to `text_leech_bot.ipynb`).
3. Fill in the form fields:
   - `GITHUB_URL`: Your repository URL
   - `API_ID`: Your Telegram API ID
   - `API_HASH`: Your Telegram API Hash
   - `BOT_TOKEN`: Your Telegram Bot Token
   - `install_ffmpeg`: `Yes`
4. Click **Runtime** -> **Run all** (or press `Ctrl+F9`).
5. Colab will clone the repository, install dependencies, configure FFmpeg, and launch the bot!

---

## 📖 How to Use the Classplus (`/cp`) Feature

### Direct Download:
1. Send `/cp` in Telegram bot.
2. When prompted:
   - Enter your **Classplus Working Token** (`x-access-token`). *(Send `no` if the content is free/unrestricted)*.
   - Enter the **Classplus URL or contentHashId** (e.g. `60b8d12345` or full URL like `https://media-cdn.classplusapp.com/drm/?contentHashId=60b8d12345`).
   - Enter the **Video / Batch Name**.
   - Choose desired **Quality** (`144`, `240`, `360`, `480`, `720`, `1080`).
   - Enter caption/watermark or send `Robin` for default.
   - Send thumbnail image URL or `no`.
3. The bot automatically resolves the stream, extracts Widevine DRM keys if needed, downloads the video, and uploads it directly to your Telegram chat.

### Batch Download via `.txt` File (`/upload`):
1. Send `/upload`.
2. Upload your `.txt` file with lines formatted as:
   ```text
   Lecture 01: https://media-cdn.classplusapp.com/drm/?contentHashId=60b8d12345
   Lecture 02: https://cpvod.testbook.com/?contentHashIdl=60b8d67890
   Lecture 03: 60b8d99999
   ```
3. Follow the bot's step-by-step prompts. The bot will download and upload every video one by one.

---

## 🛠️ Troubleshooting & FAQs

- **Q: How to get Classplus `x-access-token`?**
  - Open Classplus web portal in Chrome/Firefox.
  - Press `F12` to open Developer Tools -> Go to **Network** tab.
  - Click on any course or video and look for requests to `api.classplusapp.com`.
  - In the Request Headers, copy the value of `x-access-token`.

- **Q: Download fails with 403 Forbidden on Classplus links?**
  - Make sure your `x-access-token` is valid and active.
  - The bot automatically includes required Classplus origin and referer headers (`https://web.classplusapp.com/`).

- **Q: Bot stops on free hosting platforms after inactivity?**
  - The bot includes a built-in HTTP server listening on `PORT`. On platforms like Render or Railway, use an external monitor like [UptimeRobot](https://uptimerobot.com) to ping the URL every 5 minutes to prevent sleep.

---

## 📄 License
This project is for educational and personal backup purposes only. Please follow all terms of service of the respective platforms.
