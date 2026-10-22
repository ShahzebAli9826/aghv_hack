import os
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'''
        <w:tcMar {nsdecls("w")}>
            <w:top w:w="{top}" w:type="dxa"/>
            <w:bottom w:w="{bottom}" w:type="dxa"/>
            <w:left w:w="{left}" w:type="dxa"/>
            <w:right w:w="{right}" w:type="dxa"/>
        </w:tcMar>
    ''')
    tcPr.append(tcMar)

def create_deployment_docx(output_path="Aegis_Deployment_Guide.docx"):
    doc = Document()

    # Page Margins
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Styles & Colors
    NAVY = RGBColor(15, 23, 42)       # #0F172A
    BLUE = RGBColor(37, 99, 235)      # #2563EB
    DARK_BLUE = RGBColor(30, 58, 138) # #1E3A8A
    GRAY = RGBColor(100, 116, 139)    # #64748B
    DARK_GRAY = RGBColor(51, 65, 85)  # #334155
    CODE_COLOR = RGBColor(30, 41, 59)

    # Document Header Title
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(12)
    p_title.paragraph_format.space_after = Pt(4)
    run_title = p_title.add_run("AEGIS DISASTER INTELLIGENCE PLATFORM")
    run_title.font.name = "Calibri"
    run_title.font.size = Pt(24)
    run_title.font.bold = True
    run_title.font.color.rgb = DARK_BLUE

    # Subtitle
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(8)
    run_sub = p_sub.add_run("Comprehensive End-to-End Production Deployment Guide")
    run_sub.font.name = "Calibri"
    run_sub.font.size = Pt(13)
    run_sub.font.bold = True
    run_sub.font.color.rgb = BLUE

    # Metadata Banner
    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_meta.paragraph_format.space_after = Pt(22)
    run_meta = p_meta.add_run("Architecture: React Native Expo (Mobile/Web) + FastAPI Backend (PyTorch SegFormer & U-RNN) + AWS Cloud Services")
    run_meta.font.name = "Calibri"
    run_meta.font.size = Pt(9.5)
    run_meta.font.italic = True
    run_meta.font.color.rgb = GRAY

    # Helper text formatting functions
    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.color.rgb = DARK_BLUE
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(13)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(12.5)
        run.font.bold = True
        run.font.color.rgb = BLUE
        return p

    def add_h3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(9)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = DARK_GRAY
        return p

    def add_p(text, bold_prefix=None, space_after=4):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.font.name = "Calibri"
            r_pre.font.size = Pt(10)
            r_pre.font.bold = True
            r_pre.font.color.rgb = DARK_GRAY
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(10)
        run.font.color.rgb = DARK_GRAY
        return p

    def add_bullet(text, bold_prefix=None):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.font.name = "Calibri"
            r_pre.font.size = Pt(10)
            r_pre.font.bold = True
            r_pre.font.color.rgb = DARK_BLUE
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(10)
        run.font.color.rgb = DARK_GRAY
        return p

    def add_code_block(code_text):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        set_cell_background(cell, "F8FAFC")
        set_cell_margins(cell, top=110, bottom=110, left=170, right=170)
        
        tcPr = cell._tc.get_or_add_tcPr()
        tcBorders = parse_xml(f'''
            <w:tcBorders {nsdecls("w")}>
                <w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
                <w:left w:val="single" w:sz="16" w:space="0" w:color="2563EB"/>
                <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
                <w:right w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
            </w:tcBorders>
        ''')
        tcPr.append(tcBorders)
        
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.05
        run = p.add_run(code_text.strip())
        run.font.name = "Consolas"
        run.font.size = Pt(8.5)
        run.font.color.rgb = CODE_COLOR
        doc.add_paragraph().paragraph_format.space_after = Pt(3)

    def style_table(table, col_widths, headers, data):
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        hdr_cells = table.rows[0].cells
        for i, header_text in enumerate(headers):
            hdr_cells[i].text = header_text
            set_cell_background(hdr_cells[i], "1E3A8A")
            set_cell_margins(hdr_cells[i], top=110, bottom=110, left=130, right=130)
            p = hdr_cells[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for r in p.runs:
                r.font.name = "Calibri"
                r.font.size = Pt(9.5)
                r.font.bold = True
                r.font.color.rgb = RGBColor(255, 255, 255)

        for row_idx, row_data in enumerate(data):
            row_cells = table.add_row().cells
            bg_color = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
            for col_idx, cell_value in enumerate(row_data):
                row_cells[col_idx].text = str(cell_value)
                set_cell_background(row_cells[col_idx], bg_color)
                set_cell_margins(row_cells[col_idx], top=75, bottom=75, left=130, right=130)
                p = row_cells[col_idx].paragraphs[0]
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(9)
                    r.font.color.rgb = DARK_GRAY

        for row in table.rows:
            for idx, width in enumerate(col_widths):
                row.cells[idx].width = Inches(width)

        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # -------------------------------------------------------------
    # SECTION 1: ARCHITECTURAL OVERVIEW
    # -------------------------------------------------------------
    add_h1("1. System Architecture & Deployment Overview")
    add_p("The Aegis Disaster Intelligence Platform is comprised of two core deployable subsystems engineered for high resilience during extreme connectivity disruptions and natural disaster emergencies:")

    table = doc.add_table(rows=1, cols=4)
    headers = ["Subsystem", "Technology Stack", "Deployment Target", "Key Responsibilities"]
    arch_data = [
        ["Frontend Client", "React Native 0.86, Expo SDK 57, React Native Web", "Android APK (EAS) & Web Dashboard (Vercel / Netlify / S3)", "Field crowdsourcing, 4D nowcast map visualizer, safe route navigation, and emergency voice assistant."],
        ["Backend Engine", "FastAPI (Python 3.10+), PyTorch, Uvicorn, SQLite", "AWS EC2 / App Runner / Render / Docker Container", "Sentinel-1/2 multimodal sensor fusion, U-RNN ConvGRU depth nowcasting, DEM Dijkstra pathfinding, and MCP tools."],
        ["AI Multi-Agent Swarm", "LangGraph, Gemini 2.5 Flash, Groq LLaMA 3.3, ChromaDB", "Embedded within FastAPI Process", "Autonomous 6-agent triage, SITREP draft generation, and Human-in-the-Loop decision supervisor."],
        ["Cloud Telemetry", "AWS S3, DynamoDB, SNS, Polly, CloudWatch", "Amazon Web Services (AWS Free Tier Ready)", "Disaster telemetry logs, emergency SMS broadcast, Hindi/English neural voice synthesis, and immutable storage."]
    ]
    style_table(table, [1.3, 1.4, 1.6, 2.5], headers, arch_data)

    # -------------------------------------------------------------
    # SECTION 2: BACKEND DEPLOYMENT
    # -------------------------------------------------------------
    add_h1("2. Backend Deployment Options")
    add_p("The FastAPI backend requires Python 3.10+, PyTorch (CPU or CUDA), and access to the trained model weights file (best_model_focal.pth). Below are the four recommended deployment strategies.")

    # Strategy A: AWS EC2
    add_h2("Option A: AWS EC2 Virtual Machine (Recommended for Hackathons & Production)")
    add_p("Deploying to an AWS EC2 instance provides full control over hardware compute, native integration with AWS disaster services, and high reliability.")
    
    add_h3("Step 1: Provision EC2 Instance")
    add_bullet(" Ubuntu 22.04 LTS or 24.04 LTS (x86_64).", "AMI:")
    add_bullet(" t3.medium (2 vCPU, 4GB RAM) for lightweight CPU inference, or g4dn.xlarge for accelerated GPU inference.", "Instance Type:")
    add_bullet(" Minimum 30 GB gp3 SSD storage (to accommodate PyTorch dependencies and raster DEM data).", "Storage:")
    add_bullet(" Inbound TCP 22 (SSH), TCP 80 (HTTP), TCP 443 (HTTPS), and TCP 8000 (Backend API).", "Security Group Rules:")

    add_h3("Step 2: Server Initialization & Dependency Setup")
    add_p("Connect via SSH and install the required system libraries and Python virtual environment:")
    add_code_block("""# Update system and install required system packages
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git nginx libgl1-mesa-glx libglib2.0-0

# Clone the repository
git clone https://github.com/ShahzebAli9826/aws_hack.git
cd aws_hack/dell-flood-backend

# Create and activate Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt""")

    add_h3("Step 3: Setup Systemd Service for 24/7 Background Execution")
    add_p("Create a persistent systemd service file so the backend automatically restarts upon server reboot or process termination:")
    add_code_block("""sudo nano /etc/systemd/system/aegis-backend.service

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
WantedBy=multi-user.target""")

    add_p("Enable and start the service:")
    add_code_block("""sudo systemctl daemon-reload
sudo systemctl enable aegis-backend
sudo systemctl start aegis-backend
sudo systemctl status aegis-backend""")

    add_h3("Step 4: Configure Nginx Reverse Proxy with SSL (HTTPS)")
    add_p("Configure Nginx to proxy standard port 80/443 traffic to Uvicorn running on port 8000:")
    add_code_block("""sudo nano /etc/nginx/sites-available/aegis

server {
    listen 80;
    server_name api.yourdomain.com; # Replace with your domain or public IP

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

sudo ln -s /etc/nginx/sites-available/aegis /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Optional: Add free SSL certificate with Let's Encrypt
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.yourdomain.com""")

    # Strategy B: Docker
    add_h2("Option B: Containerized Docker Deployment")
    add_p("Packaging the backend in a container allows one-click deployments to AWS ECS, AWS App Runner, or Kubernetes.")

    add_h3("Dockerfile (for dell-flood-backend):")
    add_code_block("""FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV and raster imagery
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libgl1-mesa-glx \\
    libglib2.0-0 \\
    build-essential \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and pre-trained model weights
COPY . .

EXPOSE 8000

ENV PORT=8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]""")

    add_h3("Build and Run Commands:")
    add_code_block("""# Build docker image
docker build -t aegis-backend:latest .

# Run container with volume-mapped environment
docker run -d \\
  --name aegis-server \\
  -p 8000:8000 \\
  --env-file .env \\
  --restart unless-stopped \\
  aegis-backend:latest""")

    # Strategy C: Free PaaS
    add_h2("Option C: Free Cloud Platform Deployment (Render / Hugging Face Spaces)")
    
    add_h3("Hugging Face Spaces (Zero Cost, 16GB RAM for ML):")
    add_bullet(" Ideal for housing PyTorch deep learning models (SegFormer MiT-B2 and ConvGRU nowcaster) with zero credit card requirements.", "Why Hugging Face:")
    add_bullet(" Create Space -> Select 'Docker' -> Connect GitHub repo -> Set Port 8000.", "Procedure:")
    add_bullet(" Permanent HTTPS URL: https://<username>-aegis-backend.hf.space/api", "Resulting Endpoint:")

    add_h3("Render.com Web Service:")
    add_bullet(" Connect GitHub repository -> Root Directory: dell-flood-backend", "Build Setup:")
    add_bullet(" Build Command: pip install -r requirements.txt | Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT", "Command Settings:")

    # Strategy D: Permanent Cloudflare Named Tunnel
    add_h2("Option D: Permanent Cloudflare Named Tunnel (Zero Cost, Zero Port Forwarding)")
    add_p("If you prefer hosting on your own workstation or home server but need a fixed, permanent HTTPS URL that never changes upon reboot:")
    add_code_block("""# 1. Install Cloudflare daemon
winget install Cloudflare.cloudflared   # Windows
# or: sudo apt install cloudflared       # Linux

# 2. Authenticate tunnel
cloudflared tunnel login

# 3. Create named tunnel
cloudflared tunnel create aegis-disaster-backend

# 4. Route tunnel to your custom domain or Cloudflare DNS
cloudflared tunnel route dns aegis-disaster-backend api.yourdomain.com

# 5. Run as a permanent system service
cloudflared service install
cloudflared service start""")

    # -------------------------------------------------------------
    # SECTION 3: FRONTEND DEPLOYMENT
    # -------------------------------------------------------------
    add_h1("3. Frontend Deployment (Mobile APK & Web App)")

    add_h2("3.1 Standalone Android APK Compilation (EAS Cloud)")
    add_p("Aegis compiles into a production standalone .apk that runs on physical Android phones without requiring Expo Go or development tools.")

    add_h3("EAS Build Configuration (dell-flood-app/eas.json):")
    add_code_block("""{
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
    },
    "production": {
      "android": { "buildType": "app-bundle" }
    }
  }
}""")

    add_h3("Triggering Build via EAS CLI:")
    add_code_block("""cd dell-flood-app

# 1. Login to Expo EAS Account
npx eas-cli login

# 2. Trigger Cloud APK Compilation
npx eas-cli build --platform android --profile preview --non-interactive

# 3. View build status and download generated artifact
npx eas-cli build:list""")

    add_h2("3.2 Web Dashboard Deployment (Vercel / Netlify / AWS S3)")
    add_p("The React Native codebase compiles directly into a fast, responsive Single Page Application (SPA) for desktop browsers.")

    add_h3("Step 1: Export Static Web Bundle")
    add_code_block("""cd dell-flood-app
npx expo export -p web
# Output directory created: dell-flood-app/dist""")

    add_h3("Step 2: Deploy to Vercel (Fastest):")
    add_code_block("""# Deploy to Vercel production
npx --yes vercel deploy dist --prod

# Output URL: https://aegis-flood-app.vercel.app""")

    add_h3("Step 3: Deploy to AWS S3 & CloudFront (Enterprise Architecture):")
    add_code_block("""# Create S3 Bucket and sync files
aws s3 mb s3://aegis-web-dashboard
aws s3 sync dist/ s3://aegis-web-dashboard --acl public-read

# Enable static website hosting
aws s3 website s3://aegis-web-dashboard --index-document index.html --error-document index.html""")

    # -------------------------------------------------------------
    # SECTION 4: ENVIRONMENT VARIABLES CHECKLIST
    # -------------------------------------------------------------
    add_h1("4. Environment Variables & Secret Configuration")
    add_p("Ensure the following environment keys are populated in your deployment environment (.env files):")

    table = doc.add_table(rows=1, cols=4)
    headers = ["Key Name", "Target Service", "Required?", "Description & Purpose"]
    env_data = [
        ["EXPO_PUBLIC_API_URL", "Frontend (.env)", "Required", "Base URL pointing to the deployed FastAPI backend (/api)."],
        ["EXPO_PUBLIC_DEMO_CALL_RECIPIENT", "Frontend (.env)", "Optional", "Default recipient phone number for emergency test calls."],
        ["PORT", "Backend (.env)", "Optional", "Port for Uvicorn HTTP server (default: 8000)."],
        ["GEMINI_API_KEY", "Backend (.env)", "Required", "Google Gemini 2.5 Flash API key for the FloodRescuer emergency chatbot."],
        ["GROQ_API_KEY", "Backend (.env)", "Optional", "Groq LLaMA-3.3-70B API key used as resilient fallback LLM."],
        ["TWILIO_ACCOUNT_SID", "Backend (.env)", "Optional", "Twilio credentials for automated Hindi/English phone call dispatches."],
        ["TWILIO_AUTH_TOKEN", "Backend (.env)", "Optional", "Twilio authentication token for voice dispatch."],
        ["TWILIO_PHONE_NUMBER", "Backend (.env)", "Optional", "Twilio virtual number from which emergency voice calls originate."],
        ["SMTP_SENDER_EMAIL", "Backend (.env)", "Optional", "Sender email address for automated Situation Report emails."],
        ["SMTP_SENDER_PASSWORD", "Backend (.env)", "Optional", "App Password for SMTP gateway (e.g. Gmail 16-character token)."],
        ["ALERT_RECIPIENT_EMAIL", "Backend (.env)", "Optional", "Recipient email address for automated NDRF emergency briefings."],
        ["AWS_ACCESS_KEY_ID", "Backend (.env)", "Optional", "AWS credential for DynamoDB reports, SNS SMS alerts, and Polly TTS."],
        ["AWS_SECRET_ACCESS_KEY", "Backend (.env)", "Optional", "AWS Secret access key."],
        ["AWS_DEFAULT_REGION", "Backend (.env)", "Optional", "AWS cloud region (default: us-east-1 or ap-south-1)."]
    ]
    style_table(table, [1.8, 1.1, 0.8, 3.1], headers, env_data)

    # -------------------------------------------------------------
    # SECTION 5: AWS CLOUD RESILIENCE PROVISIONING
    # -------------------------------------------------------------
    add_h1("5. Automated AWS Disaster Cloud Provisioning")
    add_p("Aegis includes an idempotent provisioning script that automatically verifies or initializes all AWS Free Tier disaster resources:")
    add_code_block("""# Run AWS Free Tier resource setup script inside dell-flood-backend:
python -c "from app.aws.aws_provisioner import provision_all; print(provision_all())"

# Resources initialized:
# - Amazon DynamoDB: 'aegis_citizen_flood_reports' table
# - Amazon SNS: 'aegis_flood_emergency_alerts' Topic
# - Amazon S3: 'aegis-disaster-evidence-vault' Bucket
# - Amazon SQS FIFO: 'aegis_high_priority_dispatch.fifo' Queue
# - Amazon CloudWatch: 'Aegis/DisasterResponse' Custom Metric Namespace""")

    # -------------------------------------------------------------
    # SECTION 6: POST-DEPLOYMENT VERIFICATION CHECKLIST
    # -------------------------------------------------------------
    add_h1("6. Post-Deployment Verification & Smoke Tests")
    add_p("Execute this sequence of verification checks once deployment is live to ensure 100% operational readiness:")

    add_bullet(" Verify that GET / returns status: 'ONLINE' and version: '2.0.0'.", "1. Root Ping:")
    add_bullet(" Execute POST /api/run-detection?lat=25.6124&lon=85.1376 and verify the job completes all 16 steps including dynamic routing.", "2. Model Inference:")
    add_bullet(" Verify GET /api/nowcast returns valid continuous depth heatmaps for horizons 0m, 15m, 30m, and 60m.", "3. 4D Nowcasting:")
    add_bullet(" Submit a test complaint via POST /api/report-flood and confirm it appears in GET /api/complaints/list.", "4. Crowdsourcing:")
    add_bullet(" Send query to POST /api/agent/chat and confirm contextual emergency guidance is returned.", "5. AI Chatbot:")
    add_bullet(" Open the mobile APK on an Android device or test the Web Dashboard on desktop to verify seamless bidirectional communication.", "6. Client App:")

    doc.save(output_path)
    print(f"Deployment guide document successfully created at {output_path}")

if __name__ == "__main__":
    create_deployment_docx()
