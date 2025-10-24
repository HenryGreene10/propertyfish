set -euo pipefail
docker exec -it propertyfish-postgres \
  psql -U postgres -d propertyfish \
  -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_property_search;"
