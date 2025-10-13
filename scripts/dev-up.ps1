# scripts/dev-up.ps1
param([string]$DbUrl = "postgresql://postgres:postgres@localhost:5432/propertyfish")

Write-Host "Starting Postgres..." -ForegroundColor Cyan
docker compose -f infra/docker-compose.yml up -d

Write-Host "Seeding minimal schema/data..." -ForegroundColor Cyan
Get-Content infra/sql/seed_minimal.sql |
  docker exec -i propertyfish-postgres psql -U postgres -d propertyfish -v ON_ERROR_STOP=1 -f -

Write-Host "Done. DB URL: $DbUrl" -ForegroundColor Green

