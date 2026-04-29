# Deployment

## Docker Compose (recommended for development)

```bash
docker compose -f docker/docker-compose.yml up
```

This starts:
- `qdrant` — vector store on port 6333
- `konjoai` — RAG API on port 8000

The API is reachable at `http://localhost:8000` within 60 seconds.

## Kubernetes via Helm

### Prerequisites

- Helm 3.x
- A running Kubernetes cluster
- A container registry accessible from the cluster

### Install

```bash
# Add values override (minimum: set your API key)
cat > values-prod.yaml <<EOF
config:
  generatorBackend: openai
secrets:
  openaiApiKey: "sk-..."
  jwtSecretKey: "your-jwt-secret"
config:
  multiTenancyEnabled: "true"
EOF

helm install kyro ./helm/kyro -f values-prod.yaml
```

### Upgrade

```bash
helm upgrade kyro ./helm/kyro -f values-prod.yaml
```

### Key values

| Value | Default | Description |
|---|---|---|
| `replicaCount` | `2` | Pod replicas |
| `image.tag` | `1.0.0` | Image tag to deploy |
| `autoscaling.enabled` | `true` | Enable HPA |
| `autoscaling.maxReplicas` | `10` | Max pods |
| `ingress.enabled` | `false` | Enable Ingress resource |
| `qdrant.enabled` | `true` | Deploy bundled Qdrant |
| `resources.limits.memory` | `4Gi` | Per-pod memory cap |

See `helm/kyro/values.yaml` for the full reference.

### Expose via Ingress

```yaml
# values-ingress.yaml
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: kyro.your-domain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: kyro-tls
      hosts:
        - kyro.your-domain.com
```

```bash
helm upgrade kyro ./helm/kyro -f values-ingress.yaml
```

## Production checklist

- [ ] Set `JWT_SECRET_KEY` to a cryptographically random 256-bit value
- [ ] Enable `MULTI_TENANCY_ENABLED=true` and `RATE_LIMITING_ENABLED=true`
- [ ] Set `BRUTE_FORCE_ENABLED=true`
- [ ] Point `QDRANT_URL` to a managed Qdrant Cloud instance
- [ ] Set `OTEL_ENDPOINT` and `OTEL_ENABLED=true` to ship traces to your observability stack
- [ ] Configure `resources.requests` / `resources.limits` in values.yaml to match your workload
- [ ] Enable `ingress.tls` with a valid certificate
- [ ] Store secrets in a secrets manager (Vault, AWS Secrets Manager, etc.) — never in values.yaml
