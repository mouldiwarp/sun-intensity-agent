# Deployment Guide

## Deployment Options

Choose a deployment method based on your infrastructure and requirements:

| Method | Best For | Setup Time | Maintenance |
|--------|----------|-----------|-------------|
| **CLI (Cron)** | Scheduled daily jobs | 5 min | Very low |
| **Server (Standalone)** | Persistent service | 10 min | Low |
| **Docker (Standalone)** | Container orchestration | 15 min | Low |
| **Kubernetes** | Large-scale deployment | 30 min | Medium |
| **Serverless** | Event-driven, pay-per-use | 20 min | Low |

## Option 1: CLI with Cron Job

### Setup

```bash
# Install on target machine
git clone <repo-url>
cd sun-intensity-agent
pip install -r requirements.txt

# Create script
mkdir -p /opt/sun-intensity-agent
cp -r sun_intensity_agent /opt/sun-intensity-agent/
cp requirements.txt /opt/sun-intensity-agent/
```

### Configuration

Create `/opt/sun-intensity-agent/.env`:
```bash
OWM_API_KEY=sk_your_api_key
LAT=38.9
LON=-77.0
```

### Scheduling with Cron

```bash
# Edit crontab
crontab -e

# Add job (8 PM every day)
0 20 * * * cd /opt/sun-intensity-agent && /usr/bin/python3 -m sun_intensity_agent.cli >> /var/log/sun-intensity.log 2>&1

# Or with full environment
0 20 * * * source /opt/sun-intensity-agent/.env && /opt/sun-intensity-agent/venv/bin/python -m sun_intensity_agent.cli >> /var/log/sun-intensity.log 2>&1
```

### Integration Example

```bash
#!/bin/bash
# /opt/sun-intensity-agent/charge-battery.sh

export OWM_API_KEY="sk_your_key"
export LAT=38.9
export LON=-77.0

RESULT=$(python3 -m sun_intensity_agent.cli)
SCORE=$(echo "$RESULT" | jq '.score')
CHARGE_PERCENT=$((100 - SCORE))

echo "Tomorrow's sun score: $SCORE, charging to $CHARGE_PERCENT%"

# Call your battery control system
curl -X POST http://battery-api/charge -d "{\"percent\": $CHARGE_PERCENT}"
```

### Monitoring

```bash
# View logs
tail -f /var/log/sun-intensity.log

# Check cron execution
grep CRON /var/log/syslog

# Test cron job manually
cd /opt/sun-intensity-agent && python3 -m sun_intensity_agent.cli
```

---

## Option 2: Server (Standalone)

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Verify installation
python3 -m sun_intensity_agent.server
```

### Configuration

Create `.env`:
```bash
OWM_API_KEY=sk_your_api_key
LAT=38.9
LON=-77.0
PORT=8080
```

### Running the Service

**Direct:**
```bash
uvicorn sun_intensity_agent.server:app --host 0.0.0.0 --port 8080
```

**With Gunicorn** (recommended for production):
```bash
pip install gunicorn

gunicorn sun_intensity_agent.server:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080 \
  --access-logfile - \
  --error-logfile -
```

### Systemd Service

Create `/etc/systemd/system/sun-intensity.service`:
```ini
[Unit]
Description=Sun Intensity Agent
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/sun-intensity-agent
EnvironmentFile=/opt/sun-intensity-agent/.env
ExecStart=/opt/sun-intensity-agent/venv/bin/gunicorn \
  sun_intensity_agent.server:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl enable sun-intensity
sudo systemctl start sun-intensity
sudo systemctl status sun-intensity
```

### Reverse Proxy (Nginx)

```nginx
upstream sun_intensity {
    server 127.0.0.1:8080;
}

server {
    listen 80;
    server_name api.solar.local;

    location / {
        proxy_pass http://sun_intensity;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Monitoring

```bash
# Check service status
sudo systemctl status sun-intensity

# View logs
sudo journalctl -u sun-intensity -f

# Test endpoint
curl http://localhost:8080/health
curl http://localhost:8080/score
```

---

## Option 3: Docker Deployment

### Build Image

```bash
docker build -t sun-intensity-agent:latest .
```

### Run Container

**Interactive:**
```bash
docker run -it \
  -e OWM_API_KEY=sk_your_key \
  -e LAT=38.9 \
  -e LON=-77.0 \
  -p 8080:8080 \
  sun-intensity-agent:latest
```

**Detached (background):**
```bash
docker run -d \
  --name sun-intensity \
  -e OWM_API_KEY=sk_your_key \
  -e LAT=38.9 \
  -e LON=-77.0 \
  -p 8080:8080 \
  sun-intensity-agent:latest
```

### Docker Compose

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  sun-intensity:
    build: .
    container_name: sun-intensity-agent
    environment:
      OWM_API_KEY: ${OWM_API_KEY}
      LAT: ${LAT}
      LON: ${LON}
      PORT: 8080
    ports:
      - "8080:8080"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
```

**Start:**
```bash
docker-compose up -d
docker-compose logs -f
```

### Container Registry

**Push to Docker Hub:**
```bash
docker tag sun-intensity-agent:latest username/sun-intensity-agent:latest
docker push username/sun-intensity-agent:latest
```

**Pull and run:**
```bash
docker run -d \
  -e OWM_API_KEY=sk_key \
  -e LAT=38.9 \
  -e LON=-77.0 \
  -p 8080:8080 \
  username/sun-intensity-agent:latest
```

---

## Option 4: Kubernetes Deployment

### Prepare Docker Image

```bash
docker build -t sun-intensity-agent:latest .
docker tag sun-intensity-agent:latest gcr.io/my-project/sun-intensity-agent:latest
docker push gcr.io/my-project/sun-intensity-agent:latest
```

### Create ConfigMap

```bash
kubectl create configmap sun-intensity-config \
  --from-literal=LAT=38.9 \
  --from-literal=LON=-77.0
```

### Create Secret

```bash
kubectl create secret generic sun-intensity-secret \
  --from-literal=OWM_API_KEY=sk_your_key
```

### Deployment Manifest

Create `k8s/deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sun-intensity-agent
  labels:
    app: sun-intensity

spec:
  replicas: 2
  
  selector:
    matchLabels:
      app: sun-intensity
  
  template:
    metadata:
      labels:
        app: sun-intensity
    
    spec:
      containers:
      - name: sun-intensity
        image: gcr.io/my-project/sun-intensity-agent:latest
        imagePullPolicy: Always
        
        ports:
        - containerPort: 8080
          name: http
        
        env:
        - name: OWM_API_KEY
          valueFrom:
            secretKeyRef:
              name: sun-intensity-secret
              key: OWM_API_KEY
        - name: LAT
          valueFrom:
            configMapKeyRef:
              name: sun-intensity-config
              key: LAT
        - name: LON
          valueFrom:
            configMapKeyRef:
              name: sun-intensity-config
              key: LON
        - name: PORT
          value: "8080"
        
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 5
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 512Mi
```

### Service

Create `k8s/service.yaml`:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: sun-intensity-service

spec:
  selector:
    app: sun-intensity
  
  type: LoadBalancer
  
  ports:
  - port: 80
    targetPort: 8080
    protocol: TCP
```

### Deploy

```bash
# Apply manifests
kubectl apply -f k8s/

# Check deployment
kubectl get deployments
kubectl get pods
kubectl get svc

# View logs
kubectl logs -f deployment/sun-intensity-agent

# Test service
kubectl port-forward svc/sun-intensity-service 8080:80
curl http://localhost:8080/score
```

---

## Option 5: Serverless (AWS Lambda)

### Prepare Code

Install serverless dependencies:
```bash
pip install -t ./package -r requirements.txt
cp -r sun_intensity_agent ./package/
```

### Lambda Handler

Create `lambda_handler.py`:
```python
import json
from sun_intensity_agent.core import get_score
from sun_intensity_agent.errors import format_error_response, get_http_status_code

def lambda_handler(event, context):
    try:
        # Extract query parameters
        lat = event.get("queryStringParameters", {}).get("lat")
        lon = event.get("queryStringParameters", {}).get("lon")
        
        if lat:
            lat = float(lat)
        if lon:
            lon = float(lon)
        
        # Get score
        result = get_score(lat=lat, lon=lon)
        
        return {
            "statusCode": 200,
            "body": json.dumps(result),
            "headers": {"Content-Type": "application/json"}
        }
    
    except Exception as e:
        error = format_error_response(e)
        status = get_http_status_code(e)
        return {
            "statusCode": status,
            "body": json.dumps(error),
            "headers": {"Content-Type": "application/json"}
        }
```

### Deploy

Using Serverless Framework:
```bash
npm install -g serverless

# Create serverless.yml
serverless deploy \
  --aws-access-key-id xxx \
  --aws-secret-access-key yyy \
  --region us-east-1
```

---

## SSL/TLS Configuration

### Self-Signed Certificate

```bash
openssl req -x509 -newkey rsa:4096 -nodes \
  -out cert.pem -keyout key.pem -days 365
```

### Nginx with SSL

```nginx
server {
    listen 443 ssl;
    server_name api.solar.local;
    
    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
    }
}

server {
    listen 80;
    server_name api.solar.local;
    return 301 https://$server_name$request_uri;
}
```

### Uvicorn with SSL

```bash
uvicorn sun_intensity_agent.server:app \
  --ssl-keyfile=/path/to/key.pem \
  --ssl-certfile=/path/to/cert.pem \
  --host 0.0.0.0 \
  --port 443
```

---

## Environment Variables

### Required

| Variable | Example | Purpose |
|----------|---------|---------|
| `OWM_API_KEY` | `sk_xyz...` | OpenWeatherMap API key |

### Optional

| Variable | Default | Purpose |
|----------|---------|---------|
| `LAT` | — | Latitude (can be overridden per-request) |
| `LON` | — | Longitude (can be overridden per-request) |
| `PORT` | `8080` | Server port |

---

## Monitoring & Health Checks

### Health Endpoint

```bash
# Check service health
curl http://localhost:8080/health
# {"status": "ok"}
```

### Prometheus Metrics (Future)

```bash
curl http://localhost:8080/metrics
```

### Logging

**Systemd:**
```bash
sudo journalctl -u sun-intensity -f
```

**Docker:**
```bash
docker logs -f sun-intensity
```

**Kubernetes:**
```bash
kubectl logs -f deployment/sun-intensity-agent
```

---

## Backup & Recovery

### Configuration Backup

```bash
# Backup environment
cp .env .env.backup

# Backup Docker image
docker save sun-intensity-agent:latest > backup.tar

# Restore
docker load < backup.tar
```

### Database Backups (if using persistent storage)

```bash
# The agent is stateless, no database backups needed
# But backup your configuration:
git commit -m "Backup deployment config"
git push origin main
```

---

## Scaling

### Horizontal Scaling (Multiple Instances)

**Docker Compose:**
```bash
docker-compose up -d --scale sun-intensity=3
```

**Kubernetes:**
```bash
kubectl scale deployment sun-intensity-agent --replicas=5
```

### Rate Limiting Considerations

- Free OWM tier: 1,000 calls/day
- Multiple instances should share quota
- Consider API gateway rate limiting

---

## Troubleshooting Deployment

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for common issues.

---

**Last updated:** 2026-07-31  
**Status:** Production-ready
