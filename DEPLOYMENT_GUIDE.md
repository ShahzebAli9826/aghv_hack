# Aegis Disaster Intelligence Platform — Production Deployment Guide
**Version:** 2.0.0  
**Target Architecture:** React Native (Mobile APK & Web SPA) + FastAPI Backend (PyTorch SegFormer MiT-B2 & ConvGRU U-RNN) + AWS Disaster Cloud  

---

## 1. System Architecture & Overview

The **Aegis Disaster Intelligence Platform** consists of two core deployable subsystems:
1. **Frontend Client (`dell-flood-app`):** Universal React Native Expo application deployable as a standalone Android `.apk` (via EAS Cloud) and as a static Web Single Page Application (via Vercel, Netlify, or AWS S3 + CloudFront).
2. **Backend Engine (`dell-flood-backend`):** High-throughput Python FastAPI service running PyTorch deep learning inference (SegFormer SAR+Optical fusion, ConvGRU 4D depth nowcaster, DEM-based Dijkstra dynamic pathfinding, and formal MCP disaster tools).

---

## 2. Backend Deployment Strategies

### Strategy A: AWS EC2 Virtual Machine (Recommended for Hackathons & Production)
* **Instance Type:** `t3.medium` (2 vCPU, 4GB RAM) for CPU inference or `g4dn.xlarge` for GPU acceleration.
* **Operating System:** Ubuntu 22.04 LTS or 24.04 LTS.
* **Storage:** 30 GB gp3 SSD.
* **Security Group:** Inbound TCP `22` (SSH), `80` (HTTP), `443` (HTTPS), `8000` (API).

```bash
# 1. Update system packages
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git nginx libgl1-mesa-glx libglib2.0-0

# 2. Clone repository & create virtual environment
git clone https://github.com/ShahzebAli9826/aws_hack.git
cd aws_hack/dell-flood-backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Setup persistent background systemd service
sudo nano /etc/systemd/system/aegis-backend.service
```

Paste the following service definition:
```ini
[Unit]
Description=Aegis Disaster Response FastAPI Backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/aws_hack/dell-flood-backend
ExecStart=/home/ubuntu/aws_hack/dell-flood-backend/venv/bin/python main.py
Restart=always
RestartSec=5
Environment=PORT=8000
EnvironmentFile=/home/ubuntu/aws_hack/dell-flood-backend/.env

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable aegis-backend
sudo systemctl start aegis-backend
sudo systemctl status aegis-backend
```

Configure Nginx reverse proxy with SSL:
```bash
sudo nano /etc/nginx/sites-available/aegis
```
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50M;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/aegis /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Install free SSL certificate
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.yourdomain.com
```

---

### Strategy B: Docker Container Deployment
Create a `Dockerfile` in `dell-flood-backend`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
ENV PORT=8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t aegis-backend:latest .
docker run -d --name aegis-server -p 8000:8000 --env-file .env --restart unless-stopped aegis-backend:latest
```

---

### Strategy C: Free Cloud PaaS (Hugging Face Spaces / Render)
* **Hugging Face Spaces:** 100% Free with **16 GB RAM** (ideal for PyTorch models). Create a Docker Space, connect the GitHub repository, and it exposes a permanent HTTPS URL `https://<user>-aegis-backend.hf.space/api`.
* **Render.com:** Connect repository -> Root Directory: `dell-flood-backend` -> Build: `pip install -r requirements.txt` -> Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`.

---

### Strategy D: Permanent Cloudflare Named Tunnel (Zero Cost)
Host directly on your laptop or home server with a permanent domain:
```powershell
# 1. Install cloudflared
winget install Cloudflare.cloudflared

# 2. Authenticate & create named tunnel
cloudflared tunnel login
cloudflared tunnel create aegis-backend

# 3. Route to your domain & install as system service
cloudflared tunnel route dns aegis-backend api.yourdomain.com
cloudflared service install
cloudflared service start
```

---

## 3. Frontend Deployment

### 3.1 Standalone Android APK Compilation (EAS Cloud)
1. Ensure `dell-flood-app/eas.json` contains your production backend URL:
```json
{
  "cli": { "version": ">= 10.0.0", "appVersionSource": "remote" },
  "build": {
    "preview": {
      "distribution": "internal",
      "env": {
        "EXPO_PUBLIC_API_URL": "https://api.yourdomain.com/api"
      },
      "android": {
        "buildType": "apk"
      }
    }
  }
}
```
2. Trigger the cloud build:
```bash
cd dell-flood-app
npx eas-cli login
npx eas-cli build --platform android --profile preview --non-interactive
```

---

### 3.2 Web Dashboard Deployment (Vercel / Netlify / S3)
Export the static web bundle:
```bash
cd dell-flood-app
npx expo export -p web
# Generates static assets in dell-flood-app/dist
```

Deploy to Vercel in 1 command:
```bash
npx --yes vercel deploy dist --prod
```

Or deploy to AWS S3 + CloudFront:
```bash
aws s3 mb s3://aegis-disaster-dashboard
aws s3 sync dist/ s3://aegis-disaster-dashboard --acl public-read
aws s3 website s3://aegis-disaster-dashboard --index-document index.html
```

---

## 4. Environment Variables Checklist

| Variable Name | Location | Required? | Purpose |
| :--- | :--- | :--- | :--- |
| `EXPO_PUBLIC_API_URL` | Frontend (`.env`) | **Yes** | Deployed backend base URL (e.g. `https://api.yourdomain.com/api`). |
| `GEMINI_API_KEY` | Backend (`.env`) | **Yes** | Google Gemini 2.5 Flash API key for the AI disaster chatbot. |
| `GROQ_API_KEY` | Backend (`.env`) | Optional | Groq LLaMA 3.3-70B API key for resilient fallback intelligence. |
| `TWILIO_ACCOUNT_SID` | Backend (`.env`) | Optional | Twilio account SID for automated voice dispatch. |
| `TWILIO_AUTH_TOKEN` | Backend (`.env`) | Optional | Twilio authentication token. |
| `TWILIO_PHONE_NUMBER` | Backend (`.env`) | Optional | Twilio originating virtual phone number. |
| `SMTP_SENDER_EMAIL` | Backend (`.env`) | Optional | Sender address for automated situation briefings. |
| `SMTP_SENDER_PASSWORD` | Backend (`.env`) | Optional | 16-character Gmail App Password. |
| `ALERT_RECIPIENT_EMAIL`| Backend (`.env`) | Optional | Official recipient for email briefings. |
| `AWS_ACCESS_KEY_ID` | Backend (`.env`) | Optional | AWS credentials for DynamoDB, SNS, and Polly. |
| `AWS_SECRET_ACCESS_KEY`| Backend (`.env`) | Optional | AWS Secret access key. |
| `AWS_DEFAULT_REGION` | Backend (`.env`) | Optional | AWS Region (default: `us-east-1` or `ap-south-1`). |

---

## 5. Automated AWS Disaster Cloud Provisioning

Run the built-in AWS Free Tier auto-provisioning routine:
```bash
cd dell-flood-backend
python -c "from app.aws.aws_provisioner import provision_all; print(provision_all())"
```
Automatically provisions or simulates:
* **Amazon DynamoDB:** `aegis_citizen_flood_reports`
* **Amazon SNS:** `aegis_flood_emergency_alerts` Topic
* **Amazon S3:** `aegis-disaster-evidence-vault`
* **Amazon SQS FIFO:** `aegis_high_priority_dispatch.fifo`
* **Amazon CloudWatch:** `Aegis/DisasterResponse` metrics namespace

---

## 6. Post-Deployment Smoke Test Sequence

1. **Root Health Check:** `curl https://api.yourdomain.com/` $\rightarrow$ verifies `status: ONLINE`
2. **Satellite ML Pipeline:** `curl -X POST "https://api.yourdomain.com/api/run-detection?lat=25.6124&lon=85.1376"` $\rightarrow$ verifies 16-step completion
3. **4D Nowcasting:** `curl "https://api.yourdomain.com/api/nowcast?lat=25.6124&lon=85.1376"` $\rightarrow$ verifies depth horizons and Dijkstra safe routing
4. **AI Emergency Assistant:** `curl -X POST "https://api.yourdomain.com/api/agent/chat" -H "Content-Type: application/json" -d '{"message":"Where is safe high ground?"}'`
5. **Mobile APK Test:** Launch the `.apk` on an Android device to confirm live server connectivity.
