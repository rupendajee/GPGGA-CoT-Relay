# GitHub Setup and Deployment Guide

This guide will help you push your code to GitHub and deploy it on DigitalOcean.

## Step 1: Create a GitHub Repository

1. Go to [github.com](https://github.com) and sign in
2. Click the **+** icon in the top right → **New repository**
3. Name it: `gpgga-cot-relay`
4. Make it **Public** (or Private if you prefer)
5. **Don't** initialize with README, .gitignore, or license (we already have these)
6. Click **Create repository**

## Step 2: Push Your Code to GitHub

From your local machine, in the project directory:

```bash
cd /Users/rupen/Documents/STATavl\ CoT\ Relay

# Initialize git if not already done
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit of GPGGA to CoT Relay"

# Add your GitHub repository as origin
# Replace 'yourusername' with your actual GitHub username
git remote add origin https://github.com/yourusername/gpgga-cot-relay.git

# Push to GitHub
git branch -M main
git push -u origin main
```

## Step 3: Deploy on DigitalOcean

Now you can deploy on any DigitalOcean droplet with a single command!

### Option A: One-Line Deployment

SSH into your droplet and run:

```bash
curl -sSL https://raw.githubusercontent.com/yourusername/gpgga-cot-relay/main/deploy-from-github.sh | sudo bash
```

### Option B: Download and Run

```bash
# Download the deployment script
wget https://raw.githubusercontent.com/yourusername/gpgga-cot-relay/main/deploy-from-github.sh
chmod +x deploy-from-github.sh

# Edit the script to set your GitHub repo URL
nano deploy-from-github.sh
# Change GITHUB_REPO="https://github.com/yourusername/gpgga-cot-relay.git"

# Run the deployment
sudo ./deploy-from-github.sh
```

## Step 4: Configure Your TAK Server

The deployment script will prompt you to edit the `.env` file. Set your TAK server URL:

```
TAK_SERVER_URL=tcp://your-actual-tak-server.com:8087
```

## Updating Your Deployment

To update your deployment after pushing changes to GitHub:

```bash
# SSH into your droplet
ssh root@your-droplet-ip

# Run the deployment script again
/opt/gpgga-cot-relay/deploy-from-github.sh
```

Or simply:
```bash
cd /opt/gpgga-cot-relay
git pull
docker-compose build
docker-compose up -d
```

## Automated Updates

To enable automatic updates when you push to GitHub, you can set up a webhook or a cron job:

### Cron Job Method

Add this to your droplet's crontab:

```bash
# Edit crontab
crontab -e

# Add this line to check for updates every hour
0 * * * * cd /opt/gpgga-cot-relay && git pull && docker-compose build && docker-compose up -d
```

## Troubleshooting

### Permission Denied
If you get permission errors when cloning:
- For private repos, you'll need to set up SSH keys or use a personal access token
- See: https://docs.github.com/en/authentication

### Can't Connect to GitHub
Check your droplet's DNS and network connectivity:
```bash
ping github.com
nslookup github.com
```

### Docker Build Fails
Check the logs:
```bash
cd /opt/gpgga-cot-relay
docker-compose build --no-cache
```
