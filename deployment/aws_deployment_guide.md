# AWS EC2 & Docker Deployment Guide

## Cognizant (CTS) Nurture Placement Hackathon - Production Deployment

This guide outlines how to deploy the **Commercial Analytics Market Share & Share-Shift Tracker** onto AWS EC2 using Docker.

---

### STEP 1: Launch an AWS EC2 Instance

1. Log into your **AWS Management Console** and navigate to **EC2**.
2. Click **Launch Instance**:
   - **Name:** `CTS-Commercial-Analytics-Server`
   - **OS Image:** Ubuntu 22.04 LTS (Free Tier Eligible)
   - **Instance Type:** `t2.micro` or `t3.micro` (1 vCPU, 1 GiB RAM)
   - **Key Pair:** Select or create a key pair (`.pem` file) to SSH into the instance.

---

### STEP 2: Configure Security Group Inbound Rules

Add the following inbound port rules under **Edit Inbound Rules**:

| Type | Protocol | Port Range | Source | Description |
|---|---|---|---|---|
| SSH | TCP | 22 | My IP / Anywhere | Remote SSH Management |
| Custom TCP | TCP | 8501 | Anywhere (0.0.0.0/0) | Streamlit Executive Dashboard |
| Custom TCP | TCP | 8000 | Anywhere (0.0.0.0/0) | FastAPI Ingestion REST API |

---

### STEP 3: Connect & Deploy via Docker

SSH into your EC2 instance from terminal or PowerShell:

```bash
ssh -i "your-key.pem" ubuntu@YOUR_EC2_PUBLIC_IP
```

Execute the following setup commands on EC2:

```bash
# 1. Update system & install Docker
sudo apt update && sudo apt install -y docker.io docker-compose

# 2. Clone your GitHub repository
git clone https://github.com/Dharshini-1516/CTS-Commercial-Analytics.git
cd CTS-Commercial-Analytics

# 3. Build Docker image
sudo docker build -t cts-analytics -f deployment/Dockerfile .

# 4. Launch Container
sudo docker run -d \
  -p 8501:8501 \
  -p 8000:8000 \
  --name cts-app \
  cts-analytics
```

---

### STEP 4: Live URL Verification

Once deployed, access your live production links:

- **Streamlit Executive UI:** `http://YOUR_EC2_PUBLIC_IP:8501`
- **FastAPI REST API Docs:** `http://YOUR_EC2_PUBLIC_IP:8000/docs`
